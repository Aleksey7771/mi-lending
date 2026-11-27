from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
import config


class OwnerOnlyMiddleware(BaseMiddleware):
    """Block all messages not from ALLOWED_USER_ID."""

    async def __call__(
        self,
        handler: Callable[[Message, dict], Awaitable[Any]],
        event: Message,
        data: dict,
    ) -> Any:
        if not hasattr(event, "from_user") or event.from_user is None:
            return None
        if event.from_user.id != config.ALLOWED_USER_ID:
            return None
        return await handler(event, data)
