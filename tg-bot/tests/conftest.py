import os
import sys

# Set required env vars BEFORE any module imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token_123")
os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
os.environ.setdefault("ALLOWED_USER_ID", "123456789")

# add tg-bot root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import aiosqlite


@pytest.fixture
async def db(tmp_path):
    """In-memory test database with schema applied."""
    from db.database import init_db
    async with aiosqlite.connect(tmp_path / "test.db") as conn:
        conn.row_factory = aiosqlite.Row
        await init_db(conn)
        yield conn
