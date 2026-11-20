import unittest

from agents.postmately import PostmatelyClient, PostmatelyError


class FakePostmatelyClient(PostmatelyClient):
    def __init__(self, channels=None, validation=None, post=None):
        super().__init__(
            url="https://example.invalid/mcp",
            api_key="test-key",
            telegram_channel_id="",
        )
        self.channels = channels or [
            {"id": "telegram-1", "platform": "telegram", "canPublish": True}
        ]
        self.validation = validation or {"ok": True, "issues": []}
        self.post = post or {"id": "post-1", "status": "sent"}
        self.calls = []

    async def _call_tool(self, name, arguments=None, *, outcome_uncertain=False):
        self.calls.append((name, arguments, outcome_uncertain))
        if name == "list_channels":
            return self.channels
        if name == "validate_post":
            return self.validation
        if name == "create_post":
            return self.post
        raise AssertionError(f"Unexpected Postmately tool: {name}")


class PostmatelyClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_validates_a_unique_publishable_telegram_channel_before_publish(self):
        client = FakePostmatelyClient()

        channel_id = await client.validate_telegram_post("Свежая рыба сегодня")
        post = await client.publish_telegram_post("Свежая рыба сегодня", channel_id)

        self.assertEqual(channel_id, "telegram-1")
        self.assertEqual(post.post_id, "post-1")
        self.assertEqual(client.calls[1][0], "validate_post")
        self.assertEqual(client.calls[2][0], "create_post")
        self.assertEqual(client.calls[2][1]["when"], "now")
        self.assertTrue(client.calls[2][2])

    async def test_does_not_publish_when_validation_fails(self):
        client = FakePostmatelyClient(validation={"ok": False, "issues": ["too long"]})

        with self.assertRaises(PostmatelyError):
            await client.validate_telegram_post("Текст поста")

        self.assertEqual([call[0] for call in client.calls], ["list_channels", "validate_post"])

    async def test_requires_explicit_channel_when_multiple_can_publish(self):
        client = FakePostmatelyClient(
            channels=[
                {"id": "telegram-1", "platform": "telegram", "canPublish": True},
                {"id": "telegram-2", "platform": "telegram", "canPublish": True},
            ]
        )

        with self.assertRaisesRegex(PostmatelyError, "POSTMATELY_TELEGRAM_CHANNEL_ID"):
            await client.validate_telegram_post("Текст поста")

        self.assertEqual([call[0] for call in client.calls], ["list_channels"])
