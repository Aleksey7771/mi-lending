"""Generate and save a Telegram post that is waiting for owner approval."""
from typing import Any


async def run_content_worker(state: dict[str, Any]) -> dict[str, Any]:
    from agents.post_agent import generate_post
    from memory.agent_data import AgentDataStore, AgentScope
    from memory.db import AsyncSessionFactory
    from memory.models import Content

    params = state.get("params", {})
    topic = params.get("topic") or params.get("product") or state.get("task", "")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("A topic is required to generate a post")

    price = params.get("price")
    price_info = f"{price} ₽/кг" if price not in (None, "") else ""
    post_text = await generate_post(topic=topic.strip(), price_info=price_info)

    store = AgentDataStore(AgentScope.CONTENT, AsyncSessionFactory)
    content = await store.create(Content(platform="telegram", body=post_text))
    return {
        "worker": "content",
        "status": "pending_approval",
        "content_id": str(content.id),
        "text": content.body,
    }
