import os
import aiosqlite
from contextlib import asynccontextmanager

DB_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lexavlbot.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    category         TEXT CHECK(category IN ('икра','рыба','морепродукты','другое')) DEFAULT 'другое',
    form             TEXT,
    unit             TEXT DEFAULT 'кг',
    price_retail     REAL,
    price_wholesale  REAL,
    price_vip        REAL,
    min_order_wholesale INTEGER DEFAULT 1,
    volume_tiers     TEXT,
    origin           TEXT,
    description      TEXT,
    photo_file_id    TEXT,
    in_stock         INTEGER DEFAULT 1,
    seasonal_note    TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS style_profile (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_json TEXT,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS style_feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_text  TEXT,
    post_type  TEXT,
    rating     TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    """Create all tables (idempotent — uses IF NOT EXISTS)."""
    await db.executescript(_SCHEMA)
    await db.commit()


@asynccontextmanager
async def get_db():
    """Async context manager — yields an open aiosqlite.Connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await init_db(db)
        yield db
