"""Tests for DB initialisation."""
import pytest
import aiosqlite
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_init_db_creates_required_tables(tmp_path):
    """init_db must create products, settings, style_profile, style_feedback."""
    from db.database import init_db
    async with aiosqlite.connect(tmp_path / "test.db") as conn:
        await init_db(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {r[0] for r in await cursor.fetchall()}
    assert {"products", "settings", "style_profile", "style_feedback"} <= tables


async def test_init_db_is_idempotent(tmp_path):
    """Calling init_db twice must not raise."""
    from db.database import init_db
    async with aiosqlite.connect(tmp_path / "test.db") as conn:
        await init_db(conn)
        await init_db(conn)   # second call — should not raise


async def test_get_db_returns_connection(tmp_path, monkeypatch):
    """get_db() opens the DB file and enables foreign keys."""
    from db import database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", str(tmp_path / "bot.db"))
    async with dbmod.get_db() as conn:
        cursor = await conn.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1
