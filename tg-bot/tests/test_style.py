from db.style import (
    DEFAULT_PROFILE,
    add_feedback,
    get_style_profile,
    save_style_profile,
)


async def test_get_style_profile_returns_default_when_empty(db):
    profile = await get_style_profile(db)
    assert profile == DEFAULT_PROFILE


async def test_save_and_get_style_profile(db):
    custom = {**DEFAULT_PROFILE, "tone": "casual", "emoji_density": "high"}
    await save_style_profile(db, custom)
    loaded = await get_style_profile(db)
    assert loaded["tone"] == "casual"
    assert loaded["emoji_density"] == "high"


async def test_save_overwrites_previous(db):
    await save_style_profile(db, {**DEFAULT_PROFILE, "tone": "casual"})
    await save_style_profile(db, {**DEFAULT_PROFILE, "tone": "professional"})
    profile = await get_style_profile(db)
    assert profile["tone"] == "professional"


async def test_add_feedback_stores_record(db):
    await add_feedback(db, "пост текст", "post", "good")
    cursor = await db.execute("SELECT COUNT(*) FROM style_feedback")
    row = await cursor.fetchone()
    assert row[0] == 1


async def test_default_profile_has_required_keys(db):
    for key in ("tone", "emoji_density", "length", "cta_style"):
        assert key in DEFAULT_PROFILE
