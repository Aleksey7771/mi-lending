import unittest
from uuid import uuid4

from agents.postmately import PostmatelyError, PostmatelyPost
from agents.smm_workflow import (
    SmmWorkflowError,
    approve_and_publish_content,
    publish_approved_content,
)
from memory.models import Content


class FakeContentStore:
    def __init__(self, status="pending_approval"):
        self.content = Content(
            id=uuid4(),
            platform="telegram",
            body="Тестовый пост",
            status=status,
        )
        self.content.approved_by_telegram_id = None
        self.content.approved_at = None
        self.content.platform_post_id = None
        self.content.published_at = None

    async def get(self, model, content_id):
        return self.content if self.content.id == content_id else None

    async def transition_content(
        self,
        content_id,
        *,
        expected_status,
        new_status,
        changes=None,
    ):
        if self.content.id != content_id or self.content.status != expected_status:
            return None
        for field, value in (changes or {}).items():
            setattr(self.content, field, value)
        self.content.status = new_status
        return self.content


class FakePostmatelyClient:
    def __init__(self, post=None, publish_error=None):
        self.post = post or PostmatelyPost(post_id="post-1", status="sent")
        self.publish_error = publish_error
        self.published = 0

    async def validate_telegram_post(self, text):
        return "telegram-channel"

    async def publish_telegram_post(self, text, channel_id):
        self.published += 1
        if self.publish_error:
            raise self.publish_error
        return self.post


class SmmWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_publication_requires_approval_and_records_result(self):
        store = FakeContentStore()
        client = FakePostmatelyClient()

        with self.assertRaises(SmmWorkflowError):
            await publish_approved_content(
                store.content.id,
                store=store,
                postmately_client=client,
            )
        self.assertEqual(client.published, 0)

        outcome = await approve_and_publish_content(
            store.content.id,
            12345,
            store=store,
            postmately_client=client,
        )

        self.assertTrue(outcome.published)
        self.assertEqual(store.content.status, "published")
        self.assertEqual(store.content.approved_by_telegram_id, 12345)
        self.assertEqual(store.content.platform_post_id, "post-1")

    async def test_uncertain_publish_result_is_not_retried(self):
        store = FakeContentStore()
        client = FakePostmatelyClient(
            publish_error=PostmatelyError("timeout", outcome_uncertain=True)
        )

        with self.assertRaises(PostmatelyError):
            await approve_and_publish_content(
                store.content.id,
                12345,
                store=store,
                postmately_client=client,
            )

        self.assertEqual(store.content.status, "publishing")
        with self.assertRaises(SmmWorkflowError):
            await publish_approved_content(
                store.content.id,
                store=store,
                postmately_client=client,
            )
        self.assertEqual(client.published, 1)

    async def test_known_pre_publish_failure_keeps_approved_state_for_manual_retry(self):
        store = FakeContentStore()
        client = FakePostmatelyClient(
            publish_error=PostmatelyError("connection unavailable")
        )

        with self.assertRaises(PostmatelyError):
            await approve_and_publish_content(
                store.content.id,
                12345,
                store=store,
                postmately_client=client,
            )

        self.assertEqual(store.content.status, "approved")
