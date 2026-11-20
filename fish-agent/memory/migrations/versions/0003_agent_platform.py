"""Add lead, order, content, and consent tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(254)),
        sa.Column("telegram_chat_id", sa.BigInteger()),
        sa.Column("source", sa.String(100), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("delivery_address", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('new', 'qualified', 'converted', 'closed')",
            name="ck_leads_status",
        ),
    )
    op.create_index("idx_leads_status_created_at", "leads", ["status", "created_at"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("delivery_address", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'pending', 'confirmed', 'packing', "
            "'out_for_delivery', 'delivered', 'cancelled')",
            name="ck_orders_status",
        ),
    )
    op.create_index("idx_orders_lead_created_at", "orders", ["lead_id", "created_at"])
    op.create_index("idx_orders_status_created_at", "orders", ["status", "created_at"])

    op.create_table(
        "content",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_approval"),
        sa.Column("approved_by_telegram_id", sa.BigInteger()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("platform_post_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected', 'publishing', 'published')",
            name="ck_content_status",
        ),
    )
    op.create_index("idx_content_status_created_at", "content", ["status", "created_at"])

    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_consents_active_scope",
        "consents",
        ["lead_id", "channel", "purpose"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_consents_lead_channel_purpose",
        "consents",
        ["lead_id", "channel", "purpose"],
    )


def downgrade() -> None:
    op.drop_index("idx_consents_lead_channel_purpose", table_name="consents")
    op.drop_index("uq_consents_active_scope", table_name="consents")
    op.drop_table("consents")
    op.drop_index("idx_content_status_created_at", table_name="content")
    op.drop_table("content")
    op.drop_index("idx_orders_status_created_at", table_name="orders")
    op.drop_index("idx_orders_lead_created_at", table_name="orders")
    op.drop_table("orders")
    op.drop_index("idx_leads_status_created_at", table_name="leads")
    op.drop_table("leads")
