"""ad-agent entry point.

Starts:
  1. APScheduler (daily_price Mon-Fri 09:00, weekly_promo Fri 09:05, scout every 2h)
  2. Aiogram Bot polling (approve flow + owner commands)
  3. Telethon MTProto client (for Telethon groups and scout)
"""
import asyncio
import logging
import sys

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.instance import bot
from config import settings
from scheduler.jobs import build_scheduler
from agents.coordinator import stop_all, resume_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

dp = Dispatcher()


# ── Owner-only guard ──────────────────────────────────────────────────────────

def _is_owner(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == settings.owner_telegram_id


# ── Bot command handlers ──────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not _is_owner(message):
        return
    await message.answer(
        "🤖 <b>ad-agent запущен</b>\n\n"
        "Команды:\n"
        "/daily_price — отправить прайс дня сейчас\n"
        "/weekly_promo — отправить недельный промо сейчас\n"
        "/scout — запустить сканирование цен\n"
        "/status — статус агентов\n"
        "/stop — остановить всех воркеров\n"
        "/resume — возобновить воркеров",
        parse_mode="HTML",
    )


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _is_owner(message):
        return
    await message.answer("🟢 ad-agent работает. /stop — остановить.")


@dp.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    if not _is_owner(message):
        return
    stop_all()
    await message.answer("🛑 Kill-switch активирован. Воркеры остановлены.")


@dp.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    if not _is_owner(message):
        return
    resume_all()
    await message.answer("✅ Воркеры возобновлены.")


@dp.message(Command("daily_price"))
async def cmd_daily_price(message: Message) -> None:
    if not _is_owner(message):
        return
    await message.answer("⏳ Запускаю daily_price...")
    asyncio.create_task(_run_task("daily_price", {}))


@dp.message(Command("weekly_promo"))
async def cmd_weekly_promo(message: Message) -> None:
    if not _is_owner(message):
        return
    await message.answer("⏳ Запускаю weekly_promo (генерирую через Claude)...")
    asyncio.create_task(_run_task("weekly_promo", {}))


@dp.message(Command("scout"))
async def cmd_scout(message: Message) -> None:
    if not _is_owner(message):
        return
    await message.answer("🔍 Запускаю сканирование цен конкурентов...")
    asyncio.create_task(_run_task("scout", {}))


async def _run_task(task_type: str, payload: dict) -> None:
    from agents.coordinator import run_task
    try:
        result = await run_task(task_type, payload)
        wr = result.get("worker_result", {})
        logger.info("Task %s finished: %s", task_type, wr)
    except Exception as exc:
        logger.error("Task %s failed: %s", task_type, exc, exc_info=True)
        await bot.send_message(settings.owner_telegram_id, f"❌ Ошибка задачи {task_type}:\n{exc}")


# ── Approve callback handler ──────────────────────────────────────────────────

@dp.callback_query(lambda c: c.data and c.data.startswith("approve:"))
async def on_approve_callback(callback: CallbackQuery) -> None:
    from approve.flow import resolve_approve, register_pending_edit

    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Неверный формат")
        return

    _, approve_id, action = parts

    if action == "ok":
        resolved = resolve_approve(approve_id, "ok")
        if resolved:
            await callback.answer("✅ Принято")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply("✅ <b>Опубликовано</b>", parse_mode="HTML")
        else:
            await callback.answer("Уже обработано или истёк срок")

    elif action == "skip":
        resolved = resolve_approve(approve_id, "skip")
        if resolved:
            await callback.answer("❌ Пропущено")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply("❌ <b>Пропущено</b>", parse_mode="HTML")
        else:
            await callback.answer("Уже обработано")

    elif action == "edit":
        # Register that owner's next free-text message is the edited content
        register_pending_edit(callback.from_user.id, approve_id)
        await callback.answer("✏ Жду новый текст")
        await callback.message.reply(
            "✏ <b>Отправь исправленный текст следующим сообщением</b>\n"
            "<i>(только текст, без команд)</i>",
            parse_mode="HTML",
        )


# ── Edit text capture ─────────────────────────────────────────────────────────

@dp.message()
async def on_free_text(message: Message) -> None:
    """Capture edited approve text from owner."""
    if not _is_owner(message):
        return
    if not message.text or message.text.startswith("/"):
        return

    from approve.flow import consume_pending_edit, resolve_approve

    approve_id = consume_pending_edit(message.from_user.id)
    if approve_id:
        resolved = resolve_approve(approve_id, "edit", text=message.text)
        if resolved:
            await message.reply("✅ <b>Текст обновлён, отправляю</b>", parse_mode="HTML")
        else:
            await message.reply("⚠ Approve истёк или уже обработан")
    # else: ignore unknown messages silently


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Starting ad-agent...")

    # Connect Telethon (non-blocking — warns if not authorized)
    try:
        from platforms.telegram_client import get_client
        await get_client()
        logger.info("Telethon client ready")
    except Exception as exc:
        logger.warning("Telethon startup skipped: %s", exc)

    # Start scheduler
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started — jobs: %s", [j.id for j in scheduler.get_jobs()])

    # Notify owner
    try:
        await bot.send_message(settings.owner_telegram_id, "🚀 ad-agent запущен. /start для помощи.")
    except Exception as exc:
        logger.warning("Could not notify owner: %s", exc)

    logger.info("Starting Bot polling...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
