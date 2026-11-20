import unittest
from uuid import uuid4

from memory.agent_data import AgentDataStore, AgentScope
from memory.models import Consent, Content, Lead, Order


class AgentDataStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_reading_another_agents_table_is_rejected_before_database_access(self):
        def unexpected_database_access():
            raise AssertionError("database must not be accessed for a forbidden table")

        store = AgentDataStore(AgentScope.CONTENT, unexpected_database_access)

        with self.assertRaises(PermissionError):
            await store.get(Lead, uuid4())

    async def test_writing_another_agents_table_is_rejected_before_database_access(self):
        def unexpected_database_access():
            raise AssertionError("database must not be accessed for a forbidden table")

        store = AgentDataStore(AgentScope.ORDERS, unexpected_database_access)

        with self.assertRaises(PermissionError):
            await store.create(Content(platform="telegram", body="draft"))

    async def test_content_cannot_be_created_or_updated_as_already_published(self):
        def unexpected_database_access():
            raise AssertionError("database must not be accessed for a forbidden state change")

        store = AgentDataStore(AgentScope.CONTENT, unexpected_database_access)

        with self.assertRaises(PermissionError):
            await store.create(
                Content(platform="telegram", body="draft", status="published")
            )
        with self.assertRaises(PermissionError):
            await store.update(
                Content(platform="telegram", body="draft", status="published")
            )

    async def test_content_status_cannot_skip_approval(self):
        def unexpected_database_access():
            raise AssertionError("database must not be accessed for an invalid transition")

        store = AgentDataStore(AgentScope.CONTENT, unexpected_database_access)

        with self.assertRaises(ValueError):
            await store.transition_content(
                uuid4(),
                expected_status="pending_approval",
                new_status="published",
            )

    def test_scopes_are_bound_to_their_own_models(self):
        self.assertIs(AgentDataStore._MODEL_BY_SCOPE[AgentScope.LEADS], Lead)
        self.assertIs(AgentDataStore._MODEL_BY_SCOPE[AgentScope.ORDERS], Order)
        self.assertIs(AgentDataStore._MODEL_BY_SCOPE[AgentScope.CONTENT], Content)
        self.assertIs(AgentDataStore._MODEL_BY_SCOPE[AgentScope.CONSENTS], Consent)
