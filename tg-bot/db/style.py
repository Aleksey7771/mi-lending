import json

import aiosqlite

DEFAULT_PROFILE: dict = {
    "tone": "professional",
    "emoji_density": "low",
    "length": "medium",
    "cta_style": "soft",
    "sample_good": [],
    "sample_bad": [],
}


async def get_style_profile(db: aiosqlite.Connection) -> dict:
    cursor = await db.execute(
        "SELECT profile_json FROM style_profile ORDER BY id DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return dict(DEFAULT_PROFILE)
    return json.loads(row[0])


async def save_style_profile(db: aiosqlite.Connection, profile: dict) -> None:
    await db.execute(
        "INSERT INTO style_profile (profile_json) VALUES (?)",
        (json.dumps(profile, ensure_ascii=False),),
    )
    await db.commit()


async def add_feedback(
    db: aiosqlite.Connection,
    post_text: str,
    post_type: str,
    rating: str,
) -> None:
    await db.execute(
        "INSERT INTO style_feedback (post_text, post_type, rating) VALUES (?, ?, ?)",
        (post_text, post_type, rating),
    )
    await db.commit()
