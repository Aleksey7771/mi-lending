import asyncio
import logging
from datetime import datetime, timedelta, timezone

from db.catalog import get_public_catalog
from db.database import get_db
from db.dialogs import get_pending_auto_send, mark_sent, save_dialog
from ai.dialog import generate_dialog_response
from handlers.dialog_notification import notify_owner
from platforms.max_dialog import get_updates, send_message

logger = logging.getLogger(__name__)
AUTO_SEND_DELAY_SECONDS = 300


async def run_one_cycle(bot, offset: int) -> int:
    updates = await get_updates(offset)
    for update in updates:
        try:
            msg = update.get("message", {})
            text = msg.get("body", {}).get("text", "").strip()
            sender = msg.get("sender", {})
            recipient = msg.get("recipient", {})
            client_id = str(recipient.get("chat_id", ""))
            client_name = sender.get("name", "Клиент")
            if not text or not client_id:
                continue
            async with get_db() as db:
                catalog = await get_public_catalog(db)
            settings = {}
            response = await generate_dialog_response(text, catalog, settings)
            auto_send_at = (datetime.now(timezone.utc) + timedelta(seconds=AUTO_SEND_DELAY_SECONDS)).isoformat()
            async with get_db() as db:
                dialog_id = await save_dialog(db, "max", client_id, client_name, text, response, auto_send_at)
            await notify_owner(bot, dialog_id, client_name, text, response)
        except Exception as e:
            logger.error("Dialog loop error on update %s: %s", update.get("update_id"), e)
    if updates:
        offset = max(u["update_id"] for u in updates) + 1
    async with get_db() as db:
        pending = await get_pending_auto_send(db)
    for row in pending:
        try:
            ok = await send_message(row["client_id"], row["bot_response"])
            async with get_db() as db:
                if ok:
                    await mark_sent(db, row["id"])
                else:
                    logger.error("Auto-send failed for dialog %s", row["id"])
        except Exception as e:
            logger.error("Auto-send error for dialog %s: %s", row["id"], e)
    return offset


async def run_max_dialog_loop(bot) -> None:
    offset = 0
    while True:
        offset = await run_one_cycle(bot, offset)
        await asyncio.sleep(2)
