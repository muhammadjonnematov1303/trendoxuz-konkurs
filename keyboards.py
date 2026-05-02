from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from config import CHANNEL_ID


def _channel_url() -> str:
    return f"https://t.me/{CHANNEL_ID.lstrip('@')}"


def subscribe_kb() -> InlineKeyboardMarkup:
    """Obunasiz foydalanuvchi uchun."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=_channel_url())],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")],
    ])


def main_menu_kb() -> InlineKeyboardMarkup:
    """Obunasi tasdiqlangan foydalanuvchi uchun asosiy menyu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Konkursga ishtirok etish", callback_data="join_contest")],
        [InlineKeyboardButton(text="📢 Rasmiy kanal", url=_channel_url())],
    ])


def registered_kb() -> InlineKeyboardMarkup:
    """Ro'yxatdan o'tgandan so'ng."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=_channel_url())],
    ])


def contact_kb() -> ReplyKeyboardMarkup:
    """Telefon raqam so'rash uchun reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def winner_announce_kb(channel_id: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{channel_id.lstrip('@')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=url)],
    ])


def progress_bar(count: int, max_p: int, length: int = 12) -> str:
    filled = round(count / max_p * length) if max_p else 0
    return "▓" * filled + "░" * (length - filled)
