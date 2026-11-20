"""Telethon MTProto client — shared singleton for reading/writing Telegram groups."""
import logging
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import settings

logger = logging.getLogger(__name__)

_client: TelegramClient | None = None


async def get_client() -> TelegramClient:
    global _client
    if _client and _client.is_connected():
        return _client

    os.makedirs(os.path.dirname(settings.tg_session_path) or ".", exist_ok=True)
    _client = TelegramClient(
        settings.tg_session_path,
        settings.tg_api_id,
        settings.tg_api_hash,
    )
    await _client.connect()
    if not await _client.is_user_authorized():
        logger.warning(
            "Telethon session NOT authorized. Scout and posting to Telegram groups will fail. "
            "Run fish-agent auth script: cd fish-agent && .venv\\Scripts\\python tg_reader/auth.py"
        )
    else:
        logger.info("Telethon client authorized (session=%s)", settings.tg_session_path)
    return _client


async def close_client() -> None:
    global _client
    if _client:
        await _client.disconnect()
        _client = None
        logger.info("Telethon client disconnected")
