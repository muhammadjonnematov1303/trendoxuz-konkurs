import aiosqlite
from datetime import datetime
from config import DB_PATH
from logger import log


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
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
        await db.commit()
    log.info("✅  Ma'lumotlar bazasi tayyor")


async def add_participant(user_id: int, username: str | None, full_name: str, phone: str) -> bool:
    """Returns True if added, False if duplicate."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO participants (user_id, username, full_name, phone, joined_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, full_name, phone, datetime.now().isoformat()))
            await db.commit()
        await write_log("JOIN", f"user_id={user_id} | {full_name}")
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM participants") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def is_registered(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM participants WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone() is not None


async def get_all_participants() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, full_name, phone, joined_at FROM participants ORDER BY joined_at"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_random_winners(n: int = 1) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, full_name, phone FROM participants ORDER BY RANDOM() LIMIT ?", (n,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def clear_participants() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM participants") as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
        await db.execute("DELETE FROM participants")
        await db.commit()
    await write_log("CLEAR", f"O'chirildi: {count} ta ishtirokchi")
    return count


async def write_log(action: str, details: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity_log (action, details, created_at) VALUES (?, ?, ?)",
            (action, details, datetime.now().isoformat()),
        )
        await db.commit()


async def get_recent_logs(limit: int = 40) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action, details, created_at FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
