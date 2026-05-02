import ssl
import re
import asyncpg
from datetime import datetime, timezone
from config import DATABASE_URL
from logger import log

_pool: asyncpg.Pool | None = None


def _make_dsn() -> tuple[str, ssl.SSLContext | None]:
    """
    asyncpg DSN'dan sslmode va channel_binding parametrlarini o'qimaydi —
    SSL alohida context orqali uzatiladi, noto'g'ri parametrlar olib tashlanadi.
    """
    ssl_ctx = None
    if "sslmode=require" in DATABASE_URL or "sslmode=verify-full" in DATABASE_URL:
        ssl_ctx = ssl.create_default_context()

    clean = DATABASE_URL
    for param in ("sslmode", "channel_binding"):
        clean = re.sub(rf"[?&]{param}=[^&]*", "", clean)
    clean = re.sub(r"\?$", "", clean)   # bo'sh ? ni olib tashlash
    clean = re.sub(r"&&", "&", clean)   # qo'shaloq & ni tozalash
    return clean, ssl_ctx


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn, ssl_ctx = _make_dsn()
        _pool = await asyncpg.create_pool(
            dsn,
            ssl=ssl_ctx,
            min_size=1,
            max_size=5,
            command_timeout=30,
            # Neon bepul tier 5 daqiqada idle connection'larni yopadi.
            # 60s dan keyin pool o'zi connection'ni yangilaydi — timeout oldini oladi.
            max_inactive_connection_lifetime=60.0,
        )
        log.info("🔌  PostgreSQL pool yaratildi")
    return _pool


async def ping() -> bool:
    """DB jonligini tekshirish. Keepalive task ishlatadi."""
    try:
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        return True
    except Exception as e:
        log.warning(f"⚠️  DB ping xato, pool qayta yaratiladi: {e}")
        global _pool
        _pool = None   # keyingi so'rovda yangi pool ochiladi
        return False


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        log.info("🔌  PostgreSQL pool yopildi")


async def init_db() -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    user_id    BIGINT PRIMARY KEY,
                    username   TEXT,
                    full_name  TEXT NOT NULL,
                    phone      TEXT NOT NULL,
                    joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id         BIGSERIAL PRIMARY KEY,
                    action     TEXT NOT NULL,
                    details    TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_participants_joined
                ON participants(joined_at)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
        log.info("✅  PostgreSQL bazasi tayyor")
    except Exception as e:
        log.error(f"❌  DB init xatosi: {e}")
        raise


async def add_participant(
    user_id: int,
    username: str | None,
    full_name: str,
    phone: str,
) -> bool:
    """True → saqlandi | False → duplicate | Exception → boshqa xato"""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO participants (user_id, username, full_name, phone, joined_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, username, full_name, phone, datetime.now(timezone.utc),
            )
    except asyncpg.UniqueViolationError:
        return False
    except Exception as e:
        log.error(f"❌  add_participant xatosi (user_id={user_id}): {e}")
        raise

    try:
        await write_log("JOIN", f"user_id={user_id} | {full_name} | {phone}")
    except Exception as e:
        log.warning(f"⚠️  Log yozishda xato: {e}")

    log.info(f"💾  Saqlandi: {full_name} (ID: {user_id})")
    return True


async def get_count() -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM participants") or 0
    except Exception as e:
        log.error(f"❌  get_count xatosi: {e}")
        return 0


async def is_registered(user_id: int) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM participants WHERE user_id = $1", user_id
            )
            return row is not None
    except Exception as e:
        log.error(f"❌  is_registered xatosi: {e}")
        return False


async def get_all_participants() -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, username, full_name, phone, joined_at "
                "FROM participants ORDER BY joined_at"
            )
            return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_all_participants xatosi: {e}")
        return []


async def get_random_winners(n: int = 1) -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, username, full_name, phone "
                "FROM participants ORDER BY RANDOM() LIMIT $1",
                n,
            )
            return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_random_winners xatosi: {e}")
        return []


async def clear_participants() -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM participants") or 0
            await conn.execute("DELETE FROM participants")
        await write_log("CLEAR", f"O'chirildi: {count} ta ishtirokchi")
        return count
    except Exception as e:
        log.error(f"❌  clear_participants xatosi: {e}")
        raise


async def write_log(action: str, details: str = "") -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO activity_log (action, details, created_at) VALUES ($1, $2, $3)",
                action, details, datetime.now(timezone.utc),
            )
    except Exception as e:
        log.warning(f"⚠️  write_log xatosi: {e}")


async def get_recent_logs(limit: int = 40) -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT action, details, created_at FROM activity_log "
                "ORDER BY id DESC LIMIT $1",
                limit,
            )
            return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_recent_logs xatosi: {e}")
        return []


async def get_setting(key: str) -> str | None:
    """settings jadvalidan qiymat olish."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT value FROM settings WHERE key = $1", key
            )
    except Exception as e:
        log.error(f"❌  get_setting xatosi ({key}): {e}")
        return None


async def set_setting(key: str, value: str) -> None:
    """settings jadvaliga qiymat yozish (upsert)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                key, value,
            )
    except Exception as e:
        log.error(f"❌  set_setting xatosi ({key}={value}): {e}")
        raise
