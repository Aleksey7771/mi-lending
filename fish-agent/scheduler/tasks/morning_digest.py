import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from agents.price_agent import format_morning_digest
from memory.db import AsyncSessionFactory

logger = logging.getLogger(__name__)


async def send_morning_digest(bot: Bot, owner_id: int) -> None:
    try:
        async with AsyncSessionFactory() as session:
            text = await format_morning_digest(session)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Скачать PDF", callback_data="download_pdf"),
                InlineKeyboardButton(text="🔄 Обновить прайс", callback_data="refresh_preis"),
            ]
        ])
        await bot.send_message(owner_id, text, parse_mode="HTML", reply_markup=keyboard)
        logger.info("Morning digest sent to owner %d", owner_id)
    except Exception:
        logger.exception("Failed to send morning digest")
