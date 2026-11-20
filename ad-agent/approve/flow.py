"""Human-in-the-loop approve flow.

Sends a preview to the owner via Telegram Bot with inline keyboard:
  [✅ Отправить]  [✏ Изменить]  [❌ Пропустить]

Owner presses ✏ → bot prompts for edited text → owner sends text as next message.

Returns (approved: bool, final_text: str).
"""
import asyncio
import html
import logging
import uuid
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings

logger = logging.getLogger(__name__)

APPROVE_TIMEOUT_SECONDS = 3600  # 1 hour

# approve_id → asyncio.Future
_pending: dict[str, "asyncio.Future[dict]"] = {}

# owner_chat_id → approve_id waiting for edited text
_pending_edit: dict[int, str] = {}


async def request_approve(
    text: str,
    task_type: str,
    channels: list[dict],
    content_id: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Send preview to owner, wait for decision.
    Returns (True, final_text) on approve/edit, (False, "") on reject/timeout.
    """
    from bot.instance import bot

    approve_id = str(uuid.uuid4())[:8]

    channel_names = (
        ", ".join(ch.get("display_name") or ch["channel_id"] for ch in channels)
        or "—"
    )
    safe_text = html.escape(text)
    preview = (
        f"📋 <b>Превью [{task_type}]</b>\n"
        f"Каналы: {channel_names}\n\n"
        f"<code>{safe_text}</code>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить",  callback_data=f"approve:{approve_id}:ok"),
        InlineKeyboardButton(text="✏ Изменить",   callback_data=f"approve:{approve_id}:edit"),
        InlineKeyboardButton(text="❌ Пропустить", callback_data=f"approve:{approve_id}:skip"),
    ]])

    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _pending[approve_id] = future

    try:
        await bot.send_message(
            settings.owner_telegram_id,
            preview,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        logger.info("Approve request sent — task=%s approve_id=%s", task_type, approve_id)

        try:
            decision = await asyncio.wait_for(
                asyncio.shield(future), timeout=APPROVE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning("Approve timeout — task=%s approve_id=%s", task_type, approve_id)
            return False, ""

        action = decision["action"]
        if action == "ok":
            return True, decision.get("text", text)
        if action == "edit":
            return True, decision.get("text", text)
        return False, ""

    finally:
        _pending.pop(approve_id, None)
        _pending_edit.pop(settings.owner_telegram_id, None)


def resolve_approve(approve_id: str, action: str, text: str = "") -> bool:
    """
    Called by the bot's callback_query handler.
    action: 'ok' | 'edit' | 'skip'
    Returns True if the future was found and resolved.
    """
    future = _pending.get(approve_id)
    if future and not future.done():
        future.set_result({"action": action, "text": text})
        return True
    return False


def register_pending_edit(owner_id: int, approve_id: str) -> None:
    """Mark that the owner's next free-text message is an edited version for approve_id."""
    _pending_edit[owner_id] = approve_id


def consume_pending_edit(owner_id: int) -> str | None:
    """Return and clear the pending edit approve_id for this owner."""
    return _pending_edit.pop(owner_id, None)
