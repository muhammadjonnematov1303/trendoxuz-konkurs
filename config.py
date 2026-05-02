import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        print(f"[FATAL] '{key}' muhit o'zgaruvchisi o'rnatilmagan!", flush=True)
        print(f"[FATAL] Render Dashboard → Environment → Add Environment Variable", flush=True)
        sys.exit(1)
    return val


BOT_TOKEN: str = _require("BOT_TOKEN")
CHANNEL_ID: str = _require("CHANNEL_ID")
ADMIN_IDS: list[int] = [int(x.strip()) for x in _require("ADMIN_IDS").split(",")]
WEBHOOK_HOST: str = _require("WEBHOOK_HOST").rstrip("/")
DATABASE_URL: str = _require("DATABASE_URL")
MAX_PARTICIPANTS: int = int(os.getenv("MAX_PARTICIPANTS", "100"))
PORT: int = int(os.getenv("PORT", "10000"))

WEBHOOK_PATH: str = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL: str = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
