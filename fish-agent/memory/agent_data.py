"""Table-scoped data access for the new business agents."""
from collections.abc import Mapping
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import DeclarativeBase

from memory.models import Consent, Content, Lead, Order

ModelT = TypeVar("ModelT", bound=DeclarativeBase)


class AgentScope(StrEnum):
    LEADS = "leads"
    ORDERS = "orders"
    CONTENT = "content"
    CONSENTS = "consents"


_SCOPE_MODELS: dict[AgentScope, type[DeclarativeBase]] = {
    AgentScope.LEADS: Lead,
    AgentScope.ORDERS: Order,
    AgentScope.CONTENT: Content,
    AgentScope.CONSENTS: Consent,
}


class AgentDataStore:
    """Expose CRUD operations for exactly one agent-owned table."""

    _MODEL_BY_SCOPE = _SCOPE_MODELS

    def __init__(self, scope: AgentScope, session_factory) -> None:
        self._scope = scope
        self._session_factory = session_factory

    def _authorize(self, model: type[ModelT]) -> None:
        allowed_model = self._MODEL_BY_SCOPE[self._scope]
        if model is not allowed_model:
            raise PermissionError(
                f"Agent scope '{self._scope.value}' cannot access table "
                f"'{model.__tablename__}'"
            )

    def _authorize_content_transitions(
        self,
        expected_status: str,
        new_status: str,
        changes: Mapping[str, object],
    ) -> None:
        if self._scope is not AgentScope.CONTENT:
            raise PermissionError("Only the content scope can change publication state")

        allowed_changes = {
            ("pending_approval", "approved"): {
                "approved_by_telegram_id",
                "approved_at",
            },
            ("pending_approval", "rejected"): {"rejection_reason"},
            ("publishing", "approved"): set(),
            ("approved", "publishing"): set(),
            ("publishing", "publishing"): {"platform_post_id"},
            ("publishing", "published"): {"platform_post_id", "published_at"},
        }
        transition = (expected_status, new_status)
        if transition not in allowed_changes:
            raise ValueError(f"Unsupported content transition: {expected_status} -> {new_status}")
        if not set(changes).issubset(allowed_changes[transition]):
            raise ValueError("Content transition contains fields that cannot be changed")
        if transition == ("pending_approval", "approved") and not {
            "approved_by_telegram_id",
            "approved_at",
        }.issubset(changes):
            raise ValueError("Approval requires the owner ID and approval timestamp")
        if transition == ("publishing", "published") and not {
            "platform_post_id",
            "published_at",
        }.issubset(changes):
            raise ValueError("Published content requires the Postmately ID and timestamp")

    async def get(self, model: type[ModelT], row_id: UUID) -> ModelT | None:
        self._authorize(model)
        async with self._session_factory() as session:
            result = await session.execute(select(model).where(model.id == row_id))
            return result.scalar_one_or_none()

    async def list(
        self,
        model: type[ModelT],
        *,
        filters: Mapping[str, object] | None = None,
        limit: int = 100,
    ) -> list[ModelT]:
        self._authorize(model)
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        statement = select(model)
        for field, value in (filters or {}).items():
            column = getattr(model, field, None)
            if column is None:
                raise ValueError(f"Unknown field '{field}' for table '{model.__tablename__}'")
            statement = statement.where(column == value)
        statement = statement.limit(limit)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def create(self, record: ModelT) -> ModelT:
        self._authorize(type(record))
        if isinstance(record, Content) and (
            record.status != "pending_approval"
            or record.approved_by_telegram_id is not None
            or record.approved_at is not None
            or record.platform_post_id is not None
            or record.published_at is not None
        ):
            raise PermissionError("New content must begin in pending_approval state")
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def update(self, record: ModelT) -> ModelT:
        self._authorize(type(record))
        if isinstance(record, Content):
            raise PermissionError("Use transition_content to change content records")
        async with self._session_factory() as session:
            updated = await session.merge(record)
            await session.commit()
            await session.refresh(updated)
            return updated

    async def transition_content(
        self,
        content_id: UUID,
        *,
        expected_status: str,
        new_status: str,
        changes: Mapping[str, object] | None = None,
    ) -> Content | None:
        changes = changes or {}
        self._authorize_content_transitions(expected_status, new_status, changes)
        statement = (
            update(Content)
            .where(Content.id == content_id, Content.status == expected_status)
            .values(status=new_status, **changes)
            .returning(Content)
        )
        async with self._session_factory() as session:
            result = await session.execute(statement)
            content = result.scalar_one_or_none()
            await session.commit()
            return content
