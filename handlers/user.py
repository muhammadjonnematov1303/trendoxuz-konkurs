import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID, MAX_PARTICIPANTS
from database import add_participant, get_count, is_registered, get_setting
from keyboards import subscribe_kb, main_menu_kb, registered_kb, contact_kb, progress_bar
from logger import log

router = Router()

_cooldown: dict[int, float] = {}
COOLDOWN_SECONDS = 2


def _check_cooldown(user_id: int) -> bool:
    now = time.monotonic()
    if now - _cooldown.get(user_id, 0) < COOLDOWN_SECONDS:
        return False
    _cooldown[user_id] = now
    return True


async def _is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


def _welcome_text(name: str, count: int) -> str:
    bar = progress_bar(count, MAX_PARTICIPANTS)
    return (
        f"👋 Salom, <b>{name}</b>!\n\n"
        f"🎁 TrendoX Giveaway konkursiga xush kelibsiz.\n\n"
        f"👥 Ishtirokchilar: <b>{count}/{MAX_PARTICIPANTS}</b>\n"
        f"<code>{bar}</code>\n\n"
        f"Ishtirok etish uchun quyidagi tugmani bosing."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user or not _check_cooldown(user.id):
        return

    subscribed = await _is_subscribed(bot, user.id)
    count = await get_count()

    if subscribed:
        await message.answer(_welcome_text(user.full_name, count), reply_markup=main_menu_kb())
    else:
        await message.answer(
            "👋 Xush kelibsiz!\n\n"
            "🎁 TrendoX Giveaway konkursiga qatnashish uchun\n"
            "avval rasmiy kanalimizga obuna bo'lishingiz kerak.",
            reply_markup=subscribe_kb(),
        )


@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if not user:
        return

    if not _check_cooldown(user.id):
        await callback.answer("Biroz kuting...", show_alert=False)
        return

    if not await _is_subscribed(bot, user.id):
        await callback.answer(
            "❌ Obuna topilmadi.\nAvval kanalga obuna bo'ling va qayta bosing.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    count = await get_count()
    try:
        await callback.message.edit_text(
            _welcome_text(user.full_name, count),
            reply_markup=main_menu_kb(),
        )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "join_contest")
async def join_contest(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if not user:
        return

    if not _check_cooldown(user.id):
        await callback.answer("Biroz kuting...", show_alert=False)
        return

    if not await _is_subscribed(bot, user.id):
        await callback.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        return

    if await is_registered(user.id):
        await callback.answer("ℹ️ Siz allaqachon ishtirokchisiz!", show_alert=True)
        return

    count = await get_count()
    if count >= MAX_PARTICIPANTS:
        await callback.answer("❌ Ishtirokchilar to'ldi. Keyingi konkursni kuting.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "📱 <b>Telefon raqam</b>\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni ulashing.\n"
        "Quyidagi tugmani bosing 👇",
        reply_markup=contact_kb(),
    )


@router.message(F.contact)
async def handle_contact(message: Message, bot: Bot) -> None:
    user = message.from_user
    contact = message.contact

    if not user or not contact:
        return

    if contact.user_id != user.id:
        await message.answer(
            "❌ Faqat o'z telefon raqamingizni ulashing.",
            reply_markup=contact_kb(),
        )
        return

    if await is_registered(user.id):
        channel = await get_setting("channel")
        await message.answer(
            "ℹ️ Siz allaqachon konkurs ishtirokchisiz.",
            reply_markup=registered_kb(channel),
        )
        return

    count = await get_count()
    if count >= MAX_PARTICIPANTS:
        await message.answer("❌ Ishtirokchilar to'ldi. Keyingi konkursni kuting.")
        return

    if not await _is_subscribed(bot, user.id):
        await message.answer(
            "❌ Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_kb(),
        )
        return

    try:
        added = await add_participant(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            phone=contact.phone_number,
        )
    except Exception as e:
        log.error(f"❌  add_participant exception (user_id={user.id}): {e}")
        await message.answer(
            "⚠️ Texnik xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
        )
        return

    if not added:
        channel = await get_setting("channel")
        await message.answer(
            "ℹ️ Siz allaqachon konkurs ishtirokchisiz.",
            reply_markup=registered_kb(channel),
        )
        return

    new_count = await get_count()
    bar = progress_bar(new_count, MAX_PARTICIPANTS)
    channel = await get_setting("channel")
    channel_line = f"\n📢 G'olib {channel} kanalida aniqlanadi!" if channel else ""

    await message.answer(
        "✅ Siz muvaffaqiyatli konkursda qatnashdingiz!\n\n"
        f"👤 Ism: <b>{user.full_name}</b>\n"
        f"📱 Raqam: <code>{contact.phone_number}</code>\n\n"
        f"👥 Ishtirokchilar: <b>{new_count}/{MAX_PARTICIPANTS}</b>\n"
        f"<code>{bar}</code>"
        f"{channel_line}\n\n"
        "🍀 Omad tilaymiz!",
        reply_markup=registered_kb(channel),
    )
    log.info(f"✅  Yangi ishtirokchi: {user.full_name} ({user.id})")


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
