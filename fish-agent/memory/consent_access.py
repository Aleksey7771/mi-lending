"""Shared consent checks used by customer-message delivery paths."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from memory.models import Consent, Lead


class ConsentRequiredError(PermissionError):
    pass


def email_marketing_consent_exists(email_column: ColumnElement) -> ColumnElement[bool]:
    return (
        select(Consent.id)
        .join(Lead, Consent.lead_id == Lead.id)
        .where(
            func.lower(Lead.email) == func.lower(email_column),
            Consent.channel == "email",
            Consent.purpose == "marketing",
            Consent.revoked_at.is_(None),
        )
        .exists()
    )


async def require_email_marketing_consent(
    email: str,
    *,
    session_factory=None,
) -> UUID:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ConsentRequiredError("Active email marketing consent is required")

    if session_factory is None:
        from memory.db import AsyncSessionFactory

        session_factory = AsyncSessionFactory

    statement = (
        select(Consent.id)
        .join(Lead, Consent.lead_id == Lead.id)
        .where(
            func.lower(Lead.email) == normalized_email,
            Consent.channel == "email",
            Consent.purpose == "marketing",
            Consent.revoked_at.is_(None),
        )
        .limit(1)
    )
    async with session_factory() as session:
        consent_id = (await session.execute(statement)).scalar_one_or_none()
    if consent_id is None:
        raise ConsentRequiredError("Active email marketing consent is required")
    return consent_id
