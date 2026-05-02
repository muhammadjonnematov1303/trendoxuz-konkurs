import json
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT
from database import init_db
from handlers import user, admin
from logger import log

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(user.router)
dp.include_router(admin.router)


# ── Qo'shimcha endpointlar ────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    me = request.app.get("bot_info")
    username = f"@{me.username}" if me else "unknown"
    body = json.dumps({"status": "ok", "bot": username})
    return web.Response(text=body, content_type="application/json")


async def handle_root(request: web.Request) -> web.Response:
    body = json.dumps({"service": "TrendoX Giveaway Bot", "status": "running"})
    return web.Response(text=body, content_type="application/json")


# ── Startup / Shutdown ────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    log.info(f"🚀  Server ishga tushmoqda (port: {PORT})")

    await init_db()

    try:
        me = await bot.get_me()
        app["bot_info"] = me
        log.info(f"🤖  Bot: @{me.username} (ID: {me.id})")
    except Exception as e:
        log.error(f"❌  Bot ma'lumotini olishda xato: {e}")
        log.error("❌  BOT_TOKEN noto'g'ri bo'lishi mumkin!")
        raise

    try:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        log.info(f"🔗  Webhook o'rnatildi: {WEBHOOK_URL}")

        info = await bot.get_webhook_info()
        if info.url == WEBHOOK_URL:
            log.info("✅  Webhook tasdiqlandi — bot tayyor!")
        else:
            log.warning(f"⚠️  Webhook manzili kutilgancha emas: {info.url}")
    except Exception as e:
        log.error(f"❌  Webhook o'rnatishda xato: {e}")
        log.error(f"❌  WEBHOOK_HOST to'g'riligini tekshiring: {WEBHOOK_URL}")
        raise


async def on_shutdown(app: web.Application) -> None:
    log.info("🛑  Server o'chirilmoqda...")
    try:
        await bot.delete_webhook()
        log.info("✅  Webhook o'chirildi")
    except Exception as e:
        log.warning(f"⚠️  Webhook o'chirishda xato: {e}")
    finally:
        await bot.session.close()
        log.info("✅  Bot sessiyasi yopildi")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()

    # aiogram native webhook handler
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_root)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    log.info("=" * 50)
    log.info("🤖  TrendoX Giveaway Bot v2.1")
    log.info(f"🌐  WEBHOOK_URL: {WEBHOOK_URL}")
    log.info(f"🔌  PORT: {PORT}")
    log.info("=" * 50)

    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
