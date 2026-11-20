"""
ChannelAgent: publish approved posts to a Telegram channel.
"""
import logging
from datetime import datetime, timedelta

from config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.channel_id)


async def _record_publish(message_id: int, text: str) -> None:
    """Record a channel post in agent_memory for history tracking."""
    try:
        from memory.db import AsyncSessionFactory
        from memory.models import AgentMemory
        import json
        async with AsyncSessionFactory() as session:
            key = f"channel.post.{message_id}"
            record = AgentMemory(
                key=key,
                value={
                    "message_id": message_id,
                    "text": text[:500],
                    "published_at": datetime.utcnow().isoformat(),
                    "channel": settings.channel_id,
                },
            )
            session.add(record)
            await session.commit()
    except Exception as e:
        logger.warning("Failed to record channel post: %s", e)


async def get_recent_posts(limit: int = 10) -> list[dict]:
    """Return recently published channel posts from memory."""
    try:
        from sqlalchemy import select
        from memory.db import AsyncSessionFactory
        from memory.models import AgentMemory
        async with AsyncSessionFactory() as session:
            rows = (await session.execute(
                select(AgentMemory)
                .where(AgentMemory.key.like("channel.post.%"))
                .order_by(AgentMemory.updated_at.desc())
                .limit(limit)
            )).scalars().all()
        result = []
        for r in rows:
            v = r.value if isinstance(r.value, dict) else {}
            result.append({
                "message_id": v.get("message_id"),
                "text": v.get("text", ""),
                "published_at": v.get("published_at", ""),
            })
        return result
    except Exception as e:
        logger.warning("Failed to load channel history: %s", e)
        return []


async def get_pending_posts(limit: int = 5) -> list[dict]:
    """Return recently approved (👍) posts not yet published to channel."""
    try:
        from sqlalchemy import select
        from memory.db import AsyncSessionFactory
        from memory.models import StyleExample
        async with AsyncSessionFactory() as session:
            rows = (await session.execute(
                select(StyleExample)
                .where(StyleExample.feedback_score >= 1)
                .where(StyleExample.channel_posted == False)
                .order_by(StyleExample.created_at.desc())
                .limit(limit)
            )).scalars().all()
        return [{"id": r.id, "content": r.content, "created_at": r.created_at} for r in rows]
    except Exception as e:
        logger.warning("Failed to load pending posts: %s", e)
        return []


async def mark_posted(example_id: int) -> None:
    """Mark a StyleExample as posted to channel."""
    try:
        from memory.db import AsyncSessionFactory
        from memory.models import StyleExample
        async with AsyncSessionFactory() as session:
            ex = await session.get(StyleExample, example_id)
            if ex:
                ex.channel_posted = True
                await session.commit()
    except Exception as e:
        logger.warning("Failed to mark post as posted: %s", e)
