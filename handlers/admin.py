import asyncio
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import CHANNEL_ID
from database import (
    get_count, get_all_participants, get_random_winners,
    clear_participants, get_recent_logs, write_log,
)
from filters import IsAdmin
from keyboards import winner_announce_kb, progress_bar
from logger import log

import config as _cfg

router = Router()
router.message.filter(IsAdmin())

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    count = await get_count()
    max_p = _cfg.MAX_PARTICIPANTS
    bar = progress_bar(count, max_p)
    pct = round(count / max_p * 100) if max_p else 0

    await message.answer(
        f"📊 <b>Konkurs statistikasi</b>\n\n"
        f"👥 Ishtirokchilar: <b>{count}/{max_p}</b>\n"
        f"📈 To'lganlik: <b>{pct}%</b>\n"
        f"<code>{bar}</code>\n\n"
        f"📢 Kanal: {CHANNEL_ID}",
    )


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

    # 4000 belgilik bo'laklarga bo'lib yuborish
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
        ts = entry["created_at"][:16].replace("T", " ")
        detail = f" · {entry['details']}" if entry["details"] else ""
        lines.append(f"<code>{ts}</code>  <b>{entry['action']}</b>{detail}")

    text = "📜 <b>Oxirgi 40 ta harakat</b>\n\n" + "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "\n..."
    await message.answer(text)


@router.message(Command("golibni_aniqlash"))
async def cmd_golibni_aniqlash(message: Message) -> None:
    parts = (message.text or "").split()
    n = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1

    count = await get_count()
    if count == 0:
        await message.answer("❌ Ishtirokchilar yo'q.")
        return
    if n > count:
        await message.answer(f"❌ Jami {count} ta ishtirokchi bor, {n} ta g'olib tanlab bo'lmaydi.")
        return

    winners = await get_random_winners(n)
    lines = []
    for i, w in enumerate(winners, 1):
        medal = MEDAL.get(i, f"{i}.")
        uname = f"@{w['username']}" if w["username"] else "—"
        lines.append(
            f"{medal} <a href='tg://user?id={w['user_id']}'>{w['full_name']}</a>\n"
            f"    📱 <code>{w['phone']}</code> · {uname}"
        )

    await message.answer(f"🏆 <b>G'oliblar</b> ({n} ta)\n\n" + "\n\n".join(lines))
    await write_log("WINNERS_PICKED", f"n={n} | {', '.join(w['full_name'] for w in winners)}")


@router.message(Command("link"))
async def cmd_link(message: Message, bot: Bot) -> None:
    parts = (message.text or "").split()
    target_channel = parts[1] if len(parts) >= 2 else CHANNEL_ID

    try:
        chat = await bot.get_chat(target_channel)
    except Exception as e:
        await message.answer(f"❌ Kanal topilmadi: <code>{target_channel}</code>\n\n{e}")
        return

    count = await get_count()
    if count == 0:
        await message.answer("❌ Ishtirokchilar yo'q.")
        return

    channel_name = chat.title or target_channel
    status_msg = await message.answer("⏳ G'olib aniqlanmoqda...")

    # Kanalga boshlang'ich xabar
    try:
        await bot.send_message(
            target_channel,
            "🎲 <b>G'olib aniqlanmoqda...</b>\n\n"
            "Tizim ishtirokchilar orasidan g'olibni tanlayapti.",
        )
    except TelegramForbiddenError:
        await status_msg.edit_text("❌ Bot kanalga yoza olmaydi. Botni kanal admini qiling.")
        return

    # Dice animatsiyasi
    try:
        await bot.send_dice(target_channel, emoji="🎲")
    except Exception:
        pass

    # Animatsiyali progress bar
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
        target_channel,
        f"🔄 Tanlash jarayoni:\n<code>{steps[0][0]}</code>",
    )

    for bar_text, delay in steps[1:]:
        await asyncio.sleep(delay)
        try:
            await bot.edit_message_text(
                f"🔄 Tanlash jarayoni:\n<code>{bar_text}</code>",
                chat_id=target_channel,
                message_id=progress_msg.message_id,
            )
        except TelegramBadRequest:
            pass

    await asyncio.sleep(0.5)

    winners = await get_random_winners(1)
    winner = winners[0]
    uname = f"@{winner['username']}" if winner["username"] else "—"

    # Kanalga natija
    channel_text = (
        f"🎊 <b>G'olib aniqlandi!</b>\n\n"
        f"🏆 G'olib: <a href='tg://user?id={winner['user_id']}'><b>{winner['full_name']}</b></a>\n"
        f"📱 Telegram: {uname}\n\n"
        f"Tabriklaymiz! 🎉"
    )
    try:
        await bot.edit_message_text(
            channel_text,
            chat_id=target_channel,
            message_id=progress_msg.message_id,
            reply_markup=winner_announce_kb(target_channel),
        )
    except TelegramBadRequest:
        await bot.send_message(
            target_channel,
            channel_text,
            reply_markup=winner_announce_kb(target_channel),
        )

    # Admin chatiga batafsil natija
    await status_msg.edit_text(
        f"✅ <b>G'olib aniqlandi</b>\n\n"
        f"👤 Ism: <a href='tg://user?id={winner['user_id']}'>{winner['full_name']}</a>\n"
        f"📱 Raqam: <code>{winner['phone']}</code>\n"
        f"🔗 Telegram: {uname}\n"
        f"🆔 ID: <code>{winner['user_id']}</code>\n\n"
        f"📢 Kanal: {channel_name}\n"
        f"👥 Jami ishtirokchilar: {count}",
        reply_markup=winner_announce_kb(target_channel),
    )

    await write_log("LINK_WINNER", f"{winner['full_name']} ({winner['user_id']}) → {target_channel}")
    log.info(f"🏆  G'olib: {winner['full_name']} ({winner['user_id']}) → {target_channel}")
