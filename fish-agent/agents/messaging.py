"""Shared consent-gated delivery primitives for outbound customer messages."""
import asyncio
from collections.abc import Callable
from typing import Any

from memory.consent_access import require_email_marketing_consent


class OwnerApprovalRequiredError(PermissionError):
    pass


def _configured_owner_id() -> int:
    from config import settings

    return settings.owner_telegram_id


async def send_email_with_consent(
    email: str,
    approved_by_telegram_id: int,
    sender: Callable[..., None],
    *sender_args: Any,
) -> None:
    if approved_by_telegram_id != _configured_owner_id():
        raise OwnerApprovalRequiredError("Owner approval is required before sending")
    await require_email_marketing_consent(email)
    await asyncio.to_thread(sender, *sender_args)
