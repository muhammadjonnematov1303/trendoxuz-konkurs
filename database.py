import sqlite3
import aiosqlite
from datetime import datetime, timezone
from config import DB_PATH
from logger import log


async def init_db() -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # WAL mode: parallel read, tez yozish
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA foreign_keys=ON")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT,
                    full_name  TEXT NOT NULL,
                    phone      TEXT NOT NULL,
                    joined_at  TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    action     TEXT NOT NULL,
                    details    TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # Tezlashtiruvchi index
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_joined
                ON participants(joined_at)
            """)
            await db.commit()
        log.info(f"✅  Ma'lumotlar bazasi tayyor: {DB_PATH}")
    except Exception as e:
        log.error(f"❌  DB init xatosi: {e}")
        raise


async def add_participant(
    user_id: int,
    username: str | None,
    full_name: str,
    phone: str,
) -> bool:
    """
    True  → muvaffaqiyatli qo'shildi
    False → user allaqachon mavjud (duplicate)
    Exception → boshqa DB xatosi (caller hal qiladi)
    """
    joined_at = datetime.now(timezone.utc).isoformat()

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO participants (user_id, username, full_name, phone, joined_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, full_name, phone, joined_at),
            )
            await db.commit()
    except sqlite3.IntegrityError:
        # PRIMARY KEY (user_id) constraint: duplicate
        return False
    except Exception as e:
        log.error(f"❌  add_participant DB xatosi (user_id={user_id}): {e}")
        raise

    # Log yozish natijaga ta'sir qilmasin
    try:
        await _write_log("JOIN", f"user_id={user_id} | {full_name} | {phone}")
    except Exception as e:
        log.warning(f"⚠️  Log yozishda xato: {e}")

    log.info(f"💾  DB saqlandi: {full_name} (ID: {user_id})")
    return True


async def get_count() -> int:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM participants") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0
    except Exception as e:
        log.error(f"❌  get_count xatosi: {e}")
        return 0


async def is_registered(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM participants WHERE user_id=?", (user_id,)
            ) as cur:
                return await cur.fetchone() is not None
    except Exception as e:
        log.error(f"❌  is_registered xatosi: {e}")
        return False


async def get_all_participants() -> list[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, username, full_name, phone, joined_at "
                "FROM participants ORDER BY joined_at"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_all_participants xatosi: {e}")
        return []


async def get_random_winners(n: int = 1) -> list[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, username, full_name, phone "
                "FROM participants ORDER BY RANDOM() LIMIT ?",
                (n,),
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_random_winners xatosi: {e}")
        return []


async def clear_participants() -> int:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM participants") as cur:
                row = await cur.fetchone()
                count = row[0] if row else 0
            await db.execute("DELETE FROM participants")
            await db.commit()
        await _write_log("CLEAR", f"O'chirildi: {count} ta ishtirokchi")
        return count
    except Exception as e:
        log.error(f"❌  clear_participants xatosi: {e}")
        raise


async def _write_log(action: str, details: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (action, details, created_at) VALUES (?, ?, ?)",
            (action, details, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


# Public alias (handlers ishlatadi)
async def write_log(action: str, details: str = "") -> None:
    try:
        await _write_log(action, details)
    except Exception as e:
        log.warning(f"⚠️  write_log xatosi: {e}")


async def get_recent_logs(limit: int = 40) -> list[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT action, details, created_at FROM activity_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"❌  get_recent_logs xatosi: {e}")
        return []
