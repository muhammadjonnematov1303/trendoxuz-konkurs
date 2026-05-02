from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import CHANNEL_ID


def subscribe_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢  Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton(text="✅  Obuna bo'ldim", callback_data="check_sub")],
    ])


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉  Konkursga ishtirok etish", callback_data="join_contest")],
        [InlineKeyboardButton(text="📢  Kanal", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
    ])


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱  Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardMarkup:
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


def winner_announce_kb(channel_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎊  Kanalga o'tish ›", url=f"https://t.me/{channel_id.lstrip('@')}")],
    ])


def stats_kb(count: int, max_p: int) -> InlineKeyboardMarkup:
    filled = round(count / max_p * 12) if max_p else 0
    bar = "▓" * filled + "░" * (12 - filled)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"[{bar}]  {count}/{max_p}",
            callback_data="noop",
        )],
    ])
