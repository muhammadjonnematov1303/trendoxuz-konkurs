import asyncio
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID, MAX_PARTICIPANTS
from database import add_participant, get_count, is_registered
from keyboards import subscribe_kb, main_menu_kb, contact_kb, stats_kb
from logger import log

router = Router()

# Per-user cooldown: {user_id: last_action_timestamp}
_cooldown: dict[int, float] = {}
COOLDOWN_SECONDS = 2


def _check_cooldown(user_id: int) -> bool:
    """Returns True if user can proceed, False if still in cooldown."""
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


def _welcome_text(full_name: str, count: int) -> str:
    filled = round(count / MAX_PARTICIPANTS * 12) if MAX_PARTICIPANTS else 0
    bar = "▓" * filled + "░" * (12 - filled)
    return (
        f"<b>SALOM, {full_name.upper()}! 👋</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎊 TrendoX Giveaway Bot'ga xush kelibsiz!\n\n"
        f"📊 Hozirgi holat:\n"
        f"  👥 Ishtirokchilar: <b>{count}/{MAX_PARTICIPANTS}</b>\n"
        f"  [{bar}]\n\n"
        f"Konkursga ishtirok etish uchun quyidagi tugmani bosing."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    if not _check_cooldown(user.id):
        return

    subscribed = await _is_subscribed(bot, user.id)
    count = await get_count()

    if subscribed:
        await message.answer(
            _welcome_text(user.full_name, count),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"<b>XUSH KELIBSIZ! 👋</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"Konkursga ishtirok etish uchun avval kanalimizga obuna bo'ling.",
            reply_markup=subscribe_kb(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if not user:
        return

    if not _check_cooldown(user.id):
        await callback.answer("Iltimos, biroz kuting...", show_alert=False)
        return

    subscribed = await _is_subscribed(bot, user.id)
    if not subscribed:
        await callback.answer(
            "❌ Obuna topilmadi. Avval kanalga obuna bo'ling!",
            show_alert=True,
        )
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    count = await get_count()
    try:
        await callback.message.edit_text(
            _welcome_text(user.full_name, count),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "join_contest")
async def join_contest(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if not user:
        return

    if not _check_cooldown(user.id):
        await callback.answer("Iltimos, biroz kuting...", show_alert=False)
        return

    subscribed = await _is_subscribed(bot, user.id)
    if not subscribed:
        await callback.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        return

    if await is_registered(user.id):
        await callback.answer("ℹ️ Siz allaqachon ro'yxatdasiz!", show_alert=True)
        return

    count = await get_count()
    if count >= MAX_PARTICIPANTS:
        await callback.answer("❌ Ishtirokchilar limiti to'ldi!", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "<b>📱 TELEFON RAQAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni ulashing.\n\n"
        "⬇️ Quyidagi tugmani bosing:",
        reply_markup=contact_kb(),
        parse_mode="HTML",
    )


@router.message(F.contact)
async def handle_contact(message: Message) -> None:
    user = message.from_user
    contact = message.contact

    if not user or not contact:
        return

    # Faqat o'z raqamini ulashishi mumkin
    if contact.user_id != user.id:
        await message.answer(
            "❌ Iltimos, faqat o'z telefon raqamingizni ulashing.",
            parse_mode="HTML",
        )
        return

    if await is_registered(user.id):
        await message.answer(
            "ℹ️ Siz allaqachon ro'yxatdasiz!",
            parse_mode="HTML",
        )
        return

    count = await get_count()
    if count >= MAX_PARTICIPANTS:
        await message.answer("❌ Ishtirokchilar limiti to'ldi!")
        return

    subscribed = await _is_subscribed(message.bot, user.id)
    if not subscribed:
        await message.answer(
            "❌ Avval kanalga obuna bo'ling!",
            reply_markup=subscribe_kb(),
            parse_mode="HTML",
        )
        return

    added = await add_participant(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        phone=contact.phone_number,
    )

    if not added:
        await message.answer("ℹ️ Siz allaqachon ro'yxatdasiz!")
        return

    new_count = await get_count()
    filled = round(new_count / MAX_PARTICIPANTS * 12) if MAX_PARTICIPANTS else 0
    bar = "▓" * filled + "░" * (12 - filled)

    await message.answer(
        f"<b>🎊 MUVAFFAQIYATLI RO'YXATDAN O'TDINGIZ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Ismingiz: <b>{user.full_name}</b>\n"
        f"📱 Raqam: <code>{contact.phone_number}</code>\n\n"
        f"📊 Ishtirokchilar: <b>{new_count}/{MAX_PARTICIPANTS}</b>\n"
        f"[{bar}]\n\n"
        f"🍀 Omad tilaymiz!",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    log.info(f"✅  Yangi ishtirokchi: {user.full_name} (ID: {user.id})")


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
