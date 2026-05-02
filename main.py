import json
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT
from database import init_db, close_pool
from handlers import user, admin
from logger import log

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(user.router)
dp.include_router(admin.router)


# ── Endpointlar ───────────────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    me = request.app.get("bot_info")
    username = f"@{me.username}" if me else "unknown"
    body = json.dumps({"status": "ok", "bot": username})
    return web.Response(text=body, content_type="application/json")


async def handle_root(request: web.Request) -> web.Response:
    body = json.dumps({"service": "TrendoX Giveaway Bot", "status": "running"})
    return web.Response(text=body, content_type="application/json")


async def handle_set_webhook(request: web.Request) -> web.Response:
    """Admin tomonidan webhook'ni qo'lda qayta o'rnatish uchun."""
    try:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=False)
        info = await bot.get_webhook_info()
        log.info(f"🔗  Webhook qayta o'rnatildi: {info.url}")
        body = json.dumps({"ok": True, "webhook_url": info.url})
        return web.Response(text=body, content_type="application/json")
    except Exception as e:
        log.error(f"❌  Webhook o'rnatishda xato: {e}")
        body = json.dumps({"ok": False, "error": str(e)})
        return web.Response(text=body, status=500, content_type="application/json")


# ── Startup / Shutdown ────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    log.info(f"🚀  Server ishga tushmoqda (port: {PORT})")
    log.info(f"🌐  Webhook URL: {WEBHOOK_URL}")

    await init_db()

    # get_me: token noto'g'ri bo'lsa — crashlash kerak (ma'nosiz ishlash uchun sabab yo'q)
    try:
        me = await bot.get_me()
        app["bot_info"] = me
        log.info(f"🤖  Bot: @{me.username} (ID: {me.id})")
    except Exception as e:
        log.error(f"❌  BOT_TOKEN noto'g'ri: {e}")
        raise

    # set_webhook: xato bo'lsa — crash qilmaydi, faqat log yozadi
    # Render restart'larida on_shutdown delete_webhook chaqiradi va
    # keyingi startup'da set_webhook muvaffaqiyatsiz bo'lishi mumkin.
    # /setwebhook endpoint orqali qo'lda tuzatish mumkin.
    try:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        info = await bot.get_webhook_info()
        if info.url == WEBHOOK_URL:
            log.info("✅  Webhook tasdiqlandi — bot tayyor!")
        else:
            log.warning(f"⚠️  Webhook o'rnatilmadi. Hozirgi URL: '{info.url}'")
            log.warning(f"⚠️  /setwebhook endpoint'ini chaqiring: {WEBHOOK_URL.split('/webhook/')[0]}/setwebhook")
    except Exception as e:
        log.error(f"❌  Webhook xatosi: {e}")
        log.error("❌  Bot ishlaydi lekin webhook o'rnatilmadi.")
        log.error(f"❌  Qo'lda o'rnatish: GET /setwebhook")


async def on_shutdown(app: web.Application) -> None:
    log.info("🛑  Server to'xtatilmoqda...")
    await close_pool()
    try:
        await bot.session.close()
    except Exception:
        pass


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_root)
    app.router.add_get("/setwebhook", handle_set_webhook)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
