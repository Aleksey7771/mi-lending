from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from config import settings


class WhitelistMiddleware(BaseMiddleware):
    """Silently drops all updates not from OWNER_TELEGRAM_ID."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        update: Update = data.get("event_update")
        if update is None:
            return await handler(event, data)

        user = None
        if update.message:
            user = update.message.from_user
        elif update.callback_query:
            user = update.callback_query.from_user

        if user and user.id != settings.owner_telegram_id:
            # Silent drop — no log, no reply
            return None

        return await handler(event, data)
