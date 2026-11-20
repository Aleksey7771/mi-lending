import unittest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from sqlalchemy.dialects import postgresql

from agents.messaging import send_email_with_consent
from agents.messaging import OwnerApprovalRequiredError
from memory.consent_access import (
    ConsentRequiredError,
    email_marketing_consent_exists,
    require_email_marketing_consent,
)
from memory.models import Client


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, result):
        self.result = result

    async def execute(self, statement):
        return FakeResult(self.result)


class FakeSessionFactory:
    def __init__(self, result):
        self.session = FakeSession(result)

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class ConsentAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_delivery_is_blocked_when_consent_is_missing(self):
        sender = lambda: None
        denied = AsyncMock(side_effect=ConsentRequiredError("consent required"))
        delivery = AsyncMock()

        with patch("agents.messaging.require_email_marketing_consent", denied):
            with patch("agents.messaging._configured_owner_id", return_value=12345):
                with patch("agents.messaging.asyncio.to_thread", delivery):
                    with self.assertRaises(ConsentRequiredError):
                        await send_email_with_consent(
                            "buyer@example.test",
                            12345,
                            sender,
                        )

        delivery.assert_not_awaited()

    async def test_message_delivery_requires_owner_approval_before_consent_lookup(self):
        consent_check = AsyncMock()
        delivery = AsyncMock()

        with patch("agents.messaging._configured_owner_id", return_value=12345):
            with patch("agents.messaging.require_email_marketing_consent", consent_check):
                with patch("agents.messaging.asyncio.to_thread", delivery):
                    with self.assertRaises(OwnerApprovalRequiredError):
                        await send_email_with_consent(
                            "buyer@example.test",
                            99999,
                            lambda: None,
                        )

        consent_check.assert_not_awaited()
        delivery.assert_not_awaited()

    async def test_missing_active_consent_denies_email_delivery(self):
        with self.assertRaises(ConsentRequiredError):
            await require_email_marketing_consent(
                "buyer@example.test",
                session_factory=FakeSessionFactory(None),
            )

    async def test_active_consent_returns_its_record_id(self):
        consent_id = uuid4()

        result = await require_email_marketing_consent(
            "buyer@example.test",
            session_factory=FakeSessionFactory(consent_id),
        )

        self.assertEqual(result, consent_id)

    def test_outreach_filter_requires_active_email_marketing_consent(self):
        sql = str(
            email_marketing_consent_exists(Client.email).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("consents.revoked_at IS NULL", sql)
        self.assertIn("consents.channel = 'email'", sql)
        self.assertIn("consents.purpose = 'marketing'", sql)
        self.assertIn("leads.email", sql)
