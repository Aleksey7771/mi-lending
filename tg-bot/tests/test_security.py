"""Tests for OwnerOnlyMiddleware — only ALLOWED_USER_ID gets responses."""
import pytest
from unittest.mock import AsyncMock, MagicMock


async def _make_message(user_id: int):
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.text = "hello"
    return msg


async def test_unknown_user_is_blocked():
    """Middleware returns None for unknown user, handler is NOT called."""
    from middleware.owner import OwnerOnlyMiddleware
    import config as cfg

    middleware = OwnerOnlyMiddleware()
    handler = AsyncMock(return_value="response")
    msg = await _make_message(user_id=99999999)

    # patch ALLOWED_USER_ID to a known value
    original = cfg.ALLOWED_USER_ID
    cfg.ALLOWED_USER_ID = 123456789
    try:
        result = await middleware(handler, msg, {})
        assert result is None
        handler.assert_not_called()
    finally:
        cfg.ALLOWED_USER_ID = original


async def test_owner_passes_through():
    """Middleware calls handler for ALLOWED_USER_ID."""
    from middleware.owner import OwnerOnlyMiddleware
    import config as cfg

    middleware = OwnerOnlyMiddleware()
    handler = AsyncMock(return_value="response")
    msg = await _make_message(user_id=123456789)

    original = cfg.ALLOWED_USER_ID
    cfg.ALLOWED_USER_ID = 123456789
    try:
        await middleware(handler, msg, {})
        handler.assert_called_once()
    finally:
        cfg.ALLOWED_USER_ID = original
