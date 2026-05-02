import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
CHANNEL_ID: str = os.environ["CHANNEL_ID"]
ADMIN_IDS: list[int] = [int(x.strip()) for x in os.environ["ADMIN_IDS"].split(",")]
WEBHOOK_HOST: str = os.environ["WEBHOOK_HOST"].rstrip("/")
MAX_PARTICIPANTS: int = int(os.getenv("MAX_PARTICIPANTS", "100"))
DB_PATH: str = os.getenv("DB_PATH", "giveaway.db")
PORT: int = int(os.getenv("PORT", "10000"))

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
