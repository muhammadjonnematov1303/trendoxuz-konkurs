import asyncio
import json
import signal
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from config import BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT
from database import init_db
from handlers import user, admin
from logger import log

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(user.router)
dp.include_router(admin.router)


# ── Web handlers ──────────────────────────────────────────────────────────────

async def handle_webhook(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        log.error(f"❌  Webhook xatosi: {e}")
    return web.Response()


async def handle_health(request: web.Request) -> web.Response:
    me = request.app["bot_info"]
    body = json.dumps({"status": "ok", "bot": f"@{me.username}"})
    return web.Response(text=body, content_type="application/json")


async def handle_root(request: web.Request) -> web.Response:
    body = json.dumps({"service": "TrendoX Giveaway Bot", "status": "running"})
    return web.Response(text=body, content_type="application/json")


# ── Startup / Shutdown ────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    await init_db()

    me = await bot.get_me()
    app["bot_info"] = me
    log.info(f"🤖  Bot: @{me.username} (ID: {me.id})")

    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    log.info(f"🔗  Webhook o'rnatildi: {WEBHOOK_URL}")

    info = await bot.get_webhook_info()
    if info.url == WEBHOOK_URL:
        log.info("✅  Webhook tasdiqlandi")
    else:
        log.warning(f"⚠️  Webhook manzili mos emas: {info.url}")


async def on_shutdown(app: web.Application) -> None:
    log.info("🛑  Server o'chirilmoqda...")
    await bot.delete_webhook()
    await bot.session.close()
    log.info("✅  Webhook o'chirildi, ulanish yopildi")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_root)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    log.info(f"🚀  TrendoX Giveaway Bot ishga tushmoqda (port: {PORT})")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
