import asyncio
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import CHANNEL_ID
from database import (
    get_count, get_all_participants, get_random_winners,
    clear_participants, get_recent_logs, write_log,
    get_setting, set_setting,
)
from filters import IsAdmin
from keyboards import winner_announce_kb, progress_bar
from logger import log

import config as _cfg

router = Router()
router.message.filter(IsAdmin())

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

# G'olib e'loni kanalga yuboriladigan format
WINNER_POST = (
    "🎉 <b>G'OLIB ANIQLANDI! 🎉</b>\n\n"
    "🏆 G'olib: {name}\n"
    "📱 ID: <code>{user_id}</code>\n\n"
    "🎁 Sovrin: 15 ta Telegram Stars ⭐\n\n"
    "Tabriklaymiz! 🎉"
)


async def _get_channel() -> str | None:
    """Saqlangan kanaldan foydalanish, aks holda config CHANNEL_ID."""
    saved = await get_setting("channel")
    return saved or (CHANNEL_ID if CHANNEL_ID else None)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    count = await get_count()
    max_p = _cfg.MAX_PARTICIPANTS
    bar = progress_bar(count, max_p)
    pct = round(count / max_p * 100) if max_p else 0
    channel = await _get_channel() or "—"

    await message.answer(
        f"📊 <b>Konkurs statistikasi</b>\n\n"
        f"👥 Ishtirokchilar: <b>{count}/{max_p}</b>\n"
        f"📈 To'lganlik: <b>{pct}%</b>\n"
        f"<code>{bar}</code>\n\n"
        f"📢 Natija kanalı: {channel}",
    )


@router.message(Command("link"))
async def cmd_link(message: Message, bot: Bot) -> None:
    """
    /link          → hozirgi kanalni ko'rsatadi
    /link @kanal   → yangi kanal o'rnatadi
    """
    parts = (message.text or "").split()

    # Argumentsiz: hozirgi kanal ma'lumoti
    if len(parts) < 2:
        current = await get_setting("channel")
        if current:
            await message.answer(
                f"📢 Hozirgi natija kanali: <b>{current}</b>\n\n"
                f"O'zgartirish uchun: /link @yangi_kanal"
            )
        else:
            await message.answer(
                "❗ Natija kanali hali o'rnatilmagan.\n\n"
                "O'rnatish uchun: /link @kanal_username"
            )
        return

    username = parts[1]
    if not username.startswith("@"):
        username = "@" + username

    # Kanal mavjudligini tekshirish
    try:
        chat = await bot.get_chat(username)
    except Exception as e:
        await message.answer(
            f"❌ Kanal topilmadi: <code>{username}</code>\n\n"
            f"Kanal mavjudligini va bot kanal admini ekanligini tekshiring."
        )
        return

    await set_setting("channel", username)
    await write_log("CHANNEL_SET", username)

    await message.answer(
        f"✅ Natija kanali o'rnatildi!\n\n"
        f"📢 Kanal: <b>{chat.title}</b> ({username})\n\n"
        f"Endi /golibni_aniqlash natijani shu kanalga yuboradi.\n"
        f"Bot kanalda admin bo'lishi shart."
    )
    log.info(f"📢  Kanal o'rnatildi: {username}")


@router.message(Command("golibni_aniqlash"))
async def cmd_golibni_aniqlash(message: Message, bot: Bot) -> None:
    """
    Ishtirokchilar MAX_PARTICIPANTS ga yetganda 1 ta g'olib tanlaydi
    va saqlangan kanalga e'lon qiladi.
    """
    channel = await _get_channel()
    if not channel:
        await message.answer("❗ Avval /link orqali natija kanalini belgilang.")
        return

    count = await get_count()
    max_p = _cfg.MAX_PARTICIPANTS

    # Limit tekshiruvi
    if count < max_p:
        remaining = max_p - count
        bar = progress_bar(count, max_p)
        await message.answer(
            f"❗ Hali <b>{remaining} ta</b> ishtirokchi yetishmaydi.\n\n"
            f"👥 {count}/{max_p}\n"
            f"<code>{bar}</code>\n\n"
            f"G'olib faqat {max_p} ta to'lganda aniqlanadi."
        )
        return

    status_msg = await message.answer("⏳ G'olib aniqlanmoqda...")

    # Kanalga kirish tekshiruvi
    try:
        await bot.send_message(
            channel,
            "🎲 <b>G'olib aniqlanmoqda...</b>\n\n"
            "Tizim ishtirokchilar orasidan g'olibni tanlayapti.",
        )
    except TelegramForbiddenError:
        await status_msg.edit_text(
            f"❌ Bot <b>{channel}</b> kanalga yoza olmaydi.\n\n"
            f"Botni kanal admini qilib qo'shing, so'ng qayta urinib ko'ring."
        )
        return
    except Exception as e:
        await status_msg.edit_text(f"❌ Kanalga yozishda xato: {e}")
        return

    # Dice animatsiyasi
    try:
        await bot.send_dice(channel, emoji="🎲")
    except Exception:
        pass

    # Animatsiyali progress bar (5 soniya)
    steps = [
        ("▓░░░░░░░░░░░", 0.5),
        ("▓▓▓░░░░░░░░░", 0.5),
        ("▓▓▓▓▓░░░░░░░", 0.8),
        ("▓▓▓▓▓▓▓░░░░░", 0.8),
        ("▓▓▓▓▓▓▓▓▓░░░", 0.8),
        ("▓▓▓▓▓▓▓▓▓▓▓░", 0.6),
        ("▓▓▓▓▓▓▓▓▓▓▓▓", 1.0),
    ]
    progress_msg = await bot.send_message(
        channel,
        f"🔄 Tanlash jarayoni:\n<code>{steps[0][0]}</code>",
    )
    for bar_text, delay in steps[1:]:
        await asyncio.sleep(delay)
        try:
            await bot.edit_message_text(
                f"🔄 Tanlash jarayoni:\n<code>{bar_text}</code>",
                chat_id=channel,
                message_id=progress_msg.message_id,
            )
        except TelegramBadRequest:
            pass

    await asyncio.sleep(0.5)

    # G'olibni tanlash
    winners = await get_random_winners(1)
    if not winners:
        await status_msg.edit_text("❌ G'olib tanlab bo'lmadi (ro'yxat bo'sh?).")
        return

    winner = winners[0]
    uname = f"@{winner['username']}" if winner["username"] else "—"

    # Kanalga e'lon
    channel_text = WINNER_POST.format(
        name=winner["full_name"],
        user_id=winner["user_id"],
    )
    try:
        await bot.edit_message_text(
            channel_text,
            chat_id=channel,
            message_id=progress_msg.message_id,
            reply_markup=winner_announce_kb(channel),
        )
    except TelegramBadRequest:
        await bot.send_message(
            channel,
            channel_text,
            reply_markup=winner_announce_kb(channel),
        )

    # Admin chatiga batafsil natija
    await status_msg.edit_text(
        f"✅ <b>G'olib aniqlandi!</b>\n\n"
        f"👤 Ism: <a href='tg://user?id={winner['user_id']}'>{winner['full_name']}</a>\n"
        f"📱 Raqam: <code>{winner['phone']}</code>\n"
        f"🔗 Telegram: {uname}\n"
        f"🆔 ID: <code>{winner['user_id']}</code>\n\n"
        f"📢 E'lon yuborildi: {channel}\n"
        f"👥 Ishtirokchilar: {count}",
        reply_markup=winner_announce_kb(channel),
    )

    await write_log("WINNER", f"{winner['full_name']} ({winner['user_id']}) → {channel}")
    log.info(f"🏆  G'olib: {winner['full_name']} ({winner['user_id']}) → {channel}")


@router.message(Command("edit"))
async def cmd_edit(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("❌ Foydalanish: /edit 200")
        return

    new_max = int(parts[1])
    if new_max < 1:
        await message.answer("❌ Limit kamida 1 bo'lishi kerak.")
        return

    old_max = _cfg.MAX_PARTICIPANTS
    _cfg.MAX_PARTICIPANTS = new_max
    await write_log("EDIT_LIMIT", f"{old_max} → {new_max}")
    await message.answer(f"✅ Limit yangilandi: <b>{old_max} → {new_max}</b>")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    count = await clear_participants()
    await message.answer(
        f"🗑 Ro'yxat tozalandi.\n\n"
        f"O'chirilgan ishtirokchilar: <b>{count} ta</b>",
    )
    log.warning(f"⚠️  Admin {message.from_user.id} ro'yxatni tozaladi — {count} ta")


@router.message(Command("royxat"))
async def cmd_royxat(message: Message) -> None:
    participants = await get_all_participants()
    if not participants:
        await message.answer("📋 Ro'yxat hozircha bo'sh.")
        return

    header = f"📋 <b>Ishtirokchilar ro'yxati</b> ({len(participants)} ta)\n\n"
    lines = []
    for i, p in enumerate(participants, 1):
        uname = f"@{p['username']}" if p["username"] else "—"
        lines.append(
            f"{i}. <a href='tg://user?id={p['user_id']}'>{p['full_name']}</a>"
            f" · <code>{p['phone']}</code> · {uname}"
        )

    chunks, current = [], header
    for line in lines:
        if len(current) + len(line) + 1 > 4000:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)

    for chunk in chunks:
        await message.answer(chunk)


@router.message(Command("log"))
async def cmd_log(message: Message) -> None:
    logs = await get_recent_logs(40)
    if not logs:
        await message.answer("📜 Log hozircha bo'sh.")
        return

    lines = []
    for entry in logs:
        ts = str(entry["created_at"])[:16].replace("T", " ")
        detail = f" · {entry['details']}" if entry["details"] else ""
        lines.append(f"<code>{ts}</code>  <b>{entry['action']}</b>{detail}")

    text = "📜 <b>Oxirgi 40 ta harakat</b>\n\n" + "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "\n..."
    await message.answer(text)
