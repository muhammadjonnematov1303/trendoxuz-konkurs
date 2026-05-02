import asyncio
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import MAX_PARTICIPANTS, CHANNEL_ID
from database import (
    get_count, get_all_participants, get_random_winners,
    clear_participants, get_recent_logs, write_log,
)
from filters import IsAdmin
from keyboards import winner_announce_kb, stats_kb
from logger import log

import config as _cfg

router = Router()
router.message.filter(IsAdmin())


def _progress_bar(count: int, max_p: int, length: int = 12) -> str:
    filled = round(count / max_p * length) if max_p else 0
    return "▓" * filled + "░" * (length - filled)


MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    count = await get_count()
    max_p = _cfg.MAX_PARTICIPANTS
    bar = _progress_bar(count, max_p)
    pct = round(count / max_p * 100) if max_p else 0

    await message.answer(
        f"<b>📊 KONKURS STATISTIKASI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Ishtirokchilar: <b>{count}/{max_p}</b>\n"
        f"📈 To'lganlik: <b>{pct}%</b>\n"
        f"[{bar}]\n\n"
        f"📢 Kanal: {CHANNEL_ID}",
        parse_mode="HTML",
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
    await message.answer(
        f"✅ Limit yangilandi: <b>{old_max} → {new_max}</b>",
        parse_mode="HTML",
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    count = await clear_participants()
    await message.answer(
        f"🗑 <b>{count} ta ishtirokchi o'chirildi.</b>\n"
        f"Ro'yxat tozalandi.",
        parse_mode="HTML",
    )
    log.warning(f"⚠️  Admin {message.from_user.id} ro'yxatni tozaladi — {count} ta o'chirildi")


@router.message(Command("royxat"))
async def cmd_royxat(message: Message) -> None:
    participants = await get_all_participants()
    if not participants:
        await message.answer("📋 Ro'yxat bo'sh.")
        return

    lines = []
    for i, p in enumerate(participants, 1):
        uname = f"@{p['username']}" if p["username"] else "—"
        lines.append(
            f"{i}. <a href='tg://user?id={p['user_id']}'>{p['full_name']}</a> "
            f"| <code>{p['phone']}</code> | {uname}"
        )

    header = f"<b>📋 ISHTIROKCHILAR RO'YXATI ({len(participants)} ta)</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
    chunk_size = 4000
    text = header + "\n".join(lines)

    # 4000 belgilik bo'laklarga bo'lish
    chunks = []
    current = ""
    for line in (header + "\n".join(lines)).split("\n"):
        if len(current) + len(line) + 1 > chunk_size:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)

    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(Command("log"))
async def cmd_log(message: Message) -> None:
    logs = await get_recent_logs(40)
    if not logs:
        await message.answer("📜 Log bo'sh.")
        return

    lines = []
    for entry in logs:
        ts = entry["created_at"][:16].replace("T", " ")
        lines.append(f"<code>{ts}</code>  <b>{entry['action']}</b>  {entry['details'] or ''}")

    text = "<b>📜 OXIRGI 40 TA HARAKAT</b>\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "..."
    await message.answer(text, parse_mode="HTML")


@router.message(Command("golibni_aniqlash"))
async def cmd_golibni_aniqlash(message: Message) -> None:
    parts = (message.text or "").split()
    n = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1

    count = await get_count()
    if count == 0:
        await message.answer("❌ Ishtirokchilar yo'q.")
        return
    if n > count:
        await message.answer(f"❌ Ishtirokchilar soni ({count}) dan ko'p g'olib tanlab bo'lmaydi.")
        return

    winners = await get_random_winners(n)
    lines = []
    for i, w in enumerate(winners, 1):
        medal = MEDAL.get(i, f"{i}.")
        uname = f"@{w['username']}" if w["username"] else "—"
        lines.append(
            f"{medal} <a href='tg://user?id={w['user_id']}'>{w['full_name']}</a>\n"
            f"   📱 <code>{w['phone']}</code>  |  {uname}"
        )

    await message.answer(
        f"<b>🏆 G'OLIBLAR ({n} ta)</b>\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(lines),
        parse_mode="HTML",
    )
    await write_log("WINNERS_PICKED", f"n={n} | {', '.join(w['full_name'] for w in winners)}")


@router.message(Command("link"))
async def cmd_link(message: Message, bot: Bot) -> None:
    """G'olibni tanlash va kanalga e'lon qilish."""
    parts = (message.text or "").split()
    target_channel = parts[1] if len(parts) >= 2 else CHANNEL_ID

    # 1. Kanal validatsiyasi
    try:
        chat = await bot.get_chat(target_channel)
    except Exception as e:
        await message.answer(f"❌ Kanal topilmadi: <code>{target_channel}</code>\n{e}", parse_mode="HTML")
        return

    count = await get_count()
    if count == 0:
        await message.answer("❌ Ishtirokchilar yo'q — avval kimdir ro'yxatdan o'tsin.")
        return

    channel_name = chat.title or target_channel

    # 2. Admin chatiga boshlang'ich xabar
    status_msg = await message.answer(
        "⏳ <b>G'olib aniqlanmoqda...</b>",
        parse_mode="HTML",
    )

    # 3. Kanalga boshlang'ich xabar
    try:
        channel_msg = await bot.send_message(
            target_channel,
            "🎲 <b>G'OLIB ANIQLANMOQDA...</b>\n\nTizim ishtirokchilar orasidan g'olibni tanlayapti...",
            parse_mode="HTML",
        )
    except TelegramForbiddenError:
        await status_msg.edit_text("❌ Bot kanalda admin emas yoki kanalga yoza olmaydi.")
        return

    # 4. Dice animatsiyasi
    try:
        await bot.send_dice(target_channel, emoji="🎲")
    except Exception:
        pass

    # 5. Animatsiyali progress bar (5 soniya)
    steps = [
        ("[▓░░░░░░░░░░░]", 0.5),
        ("[▓▓▓░░░░░░░░░]", 0.5),
        ("[▓▓▓▓▓░░░░░░░]", 0.8),
        ("[▓▓▓▓▓▓▓░░░░░]", 0.8),
        ("[▓▓▓▓▓▓▓▓▓░░░]", 0.8),
        ("[▓▓▓▓▓▓▓▓▓▓▓░]", 0.6),
        ("[▓▓▓▓▓▓▓▓▓▓▓▓]", 1.0),
    ]

    progress_msg = await bot.send_message(
        target_channel,
        f"🔄 Tanlash jarayoni:\n{steps[0][0]}",
        parse_mode="HTML",
    )

    for bar_text, delay in steps[1:]:
        await asyncio.sleep(delay)
        try:
            await bot.edit_message_text(
                f"🔄 Tanlash jarayoni:\n{bar_text}",
                chat_id=target_channel,
                message_id=progress_msg.message_id,
            )
        except TelegramBadRequest:
            pass

    await asyncio.sleep(0.5)

    # 6. G'olibni tanlash
    winners = await get_random_winners(1)
    winner = winners[0]
    uname = f"@{winner['username']}" if winner["username"] else "—"

    # 7. Kanalga natija
    announce_text = (
        f"🎊 <b>G'OLIB ANIQLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 G'olib: <a href='tg://user?id={winner['user_id']}'><b>{winner['full_name']}</b></a>\n"
        f"📱 Telegram: {uname}\n\n"
        f"🎉 Tabriklaymiz!\n"
        f"📢 Kanal: {channel_name}"
    )

    try:
        await bot.edit_message_text(
            announce_text,
            chat_id=target_channel,
            message_id=progress_msg.message_id,
            reply_markup=winner_announce_kb(target_channel),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        await bot.send_message(
            target_channel,
            announce_text,
            reply_markup=winner_announce_kb(target_channel),
            parse_mode="HTML",
        )

    # 8. Admin chatiga natija
    admin_text = (
        f"<b>✅ G'OLIB ANIQLANDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ism: <a href='tg://user?id={winner['user_id']}'>{winner['full_name']}</a>\n"
        f"📱 Raqam: <code>{winner['phone']}</code>\n"
        f"🔗 Telegram: {uname}\n"
        f"🆔 ID: <code>{winner['user_id']}</code>\n\n"
        f"📢 Kanal: {channel_name}\n"
        f"👥 Jami ishtirokchilar: {count}"
    )

    await status_msg.edit_text(
        admin_text,
        reply_markup=winner_announce_kb(target_channel),
        parse_mode="HTML",
    )

    await write_log("LINK_WINNER", f"{winner['full_name']} (ID: {winner['user_id']}) → {target_channel}")
    log.info(f"🏆  G'olib: {winner['full_name']} (ID: {winner['user_id']}) → {target_channel}")
