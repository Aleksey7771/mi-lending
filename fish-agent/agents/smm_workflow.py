"""Approval-gated workflow for Telegram content publishing."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from agents.postmately import PostmatelyClient, PostmatelyError
from memory.agent_data import AgentDataStore, AgentScope
from memory.models import Content


class SmmWorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicationOutcome:
    post_id: str
    status: str
    published: bool


def _content_store() -> AgentDataStore:
    from memory.db import AsyncSessionFactory

    return AgentDataStore(AgentScope.CONTENT, AsyncSessionFactory)


async def approve_and_publish_content(
    content_id: UUID,
    owner_telegram_id: int,
    *,
    store: AgentDataStore | None = None,
    postmately_client: PostmatelyClient | None = None,
) -> PublicationOutcome:
    store = store or _content_store()
    content = await store.transition_content(
        content_id,
        expected_status="pending_approval",
        new_status="approved",
        changes={
            "approved_by_telegram_id": owner_telegram_id,
            "approved_at": datetime.now(timezone.utc),
        },
    )
    if content is None:
        raise SmmWorkflowError("Пост уже обработан или не найден.")
    return await publish_approved_content(
        content_id,
        store=store,
        postmately_client=postmately_client,
    )


async def reject_content(
    content_id: UUID,
    *,
    store: AgentDataStore | None = None,
) -> bool:
    store = store or _content_store()
    rejected = await store.transition_content(
        content_id,
        expected_status="pending_approval",
        new_status="rejected",
        changes={"rejection_reason": "Rejected by owner"},
    )
    return rejected is not None


async def publish_approved_content(
    content_id: UUID,
    *,
    store: AgentDataStore | None = None,
    postmately_client: PostmatelyClient | None = None,
) -> PublicationOutcome:
    store = store or _content_store()
    content = await store.get(Content, content_id)
    if content is None or content.status != "approved":
        raise SmmWorkflowError("Опубликовать можно только одобренный черновик.")

    client = postmately_client or PostmatelyClient()
    channel_id = await client.validate_telegram_post(content.body)
    claimed = await store.transition_content(
        content_id,
        expected_status="approved",
        new_status="publishing",
    )
    if claimed is None:
        raise SmmWorkflowError("Пост уже отправляется или был обработан.")

    try:
        post = await client.publish_telegram_post(content.body, channel_id)
    except PostmatelyError as error:
        if not error.outcome_uncertain:
            await store.transition_content(
                content_id,
                expected_status="publishing",
                new_status="approved",
            )
        raise

    published = post.status == "sent"
    changes = {"platform_post_id": post.post_id}
    if published:
        changes["published_at"] = datetime.now(timezone.utc)
    updated = await store.transition_content(
        content_id,
        expected_status="publishing",
        new_status="published" if published else "publishing",
        changes=changes,
    )
    if updated is None:
        raise SmmWorkflowError(
            "Postmately принял пост, но результат не удалось сохранить в базе."
        )
    return PublicationOutcome(post_id=post.post_id, status=post.status, published=published)
