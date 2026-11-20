"""Add ad-agent tables: publish_channels, ad_log, price_intel, email_inbox,
email_outbox, funnel_stages, cart_items, payments.
Also adds leads.score, orders.excel_source columns.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ALTER existing tables ────────────────────────────────────────────────
    op.add_column("leads", sa.Column("score", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("excel_source", sa.Boolean(), nullable=False, server_default="false"))

    # ── publish_channels ─────────────────────────────────────────────────────
    # Allowed publishing destinations — enforces Rule 1 (no cold outreach).
    op.create_table(
        "publish_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("added_by", sa.BigInteger(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "platform IN ('telegram','avito','forpost','yula','instagram','vk','tiktok','max')",
            name="ck_pc_platform",
        ),
        sa.CheckConstraint(
            "purpose IN ('daily_price','weekly_promo','any')",
            name="ck_pc_purpose",
        ),
    )
    op.create_index(
        "uq_pc_platform_channel_purpose",
        "publish_channels",
        ["platform", "channel_id", "purpose"],
        unique=True,
    )
    op.create_index(
        "idx_pc_active_purpose",
        "publish_channels",
        ["is_active", "purpose"],
    )

    # ── ad_log ────────────────────────────────────────────────────────────────
    op.create_table(
        "ad_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content.id", ondelete="SET NULL")),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("error_msg", sa.Text()),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "action IN ('posted','sent','failed','skipped')",
            name="ck_adlog_action",
        ),
    )
    op.create_index("idx_adlog_platform_created", "ad_log", ["platform", "created_at"])
    op.create_index("idx_adlog_content", "ad_log", ["content_id"])

    # ── price_intel ───────────────────────────────────────────────────────────
    op.create_table(
        "price_intel",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("raw_text", sa.Text()),
        sa.Column("product_name", sa.String(200)),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("price_rub", sa.Numeric(10, 2)),
        sa.Column("unit", sa.String(20), server_default="кг"),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("message_id", sa.BigInteger()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "source_type IN ('telegram','website')",
            name="ck_pi_source_type",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_pi_confidence",
        ),
    )
    op.create_index("idx_pi_product_time", "price_intel", ["product_id", "recorded_at"])
    op.create_index("idx_pi_source_time", "price_intel", ["source_name", "recorded_at"])
    op.create_index("idx_pi_message_id", "price_intel", ["source_type", "message_id"])

    # ── email_inbox ───────────────────────────────────────────────────────────
    op.create_table(
        "email_inbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False, unique=True),
        sa.Column("from_addr", sa.String(255), nullable=False),
        sa.Column("subject", sa.Text()),
        sa.Column("body_text", sa.Text()),
        sa.Column("body_html", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="unread"),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('unread','read','processed','ignored')",
            name="ck_einbox_status",
        ),
    )
    op.create_index("idx_einbox_status_recv", "email_inbox", ["status", "received_at"])
    op.create_index("idx_einbox_lead", "email_inbox", ["lead_id"])

    # ── email_outbox ──────────────────────────────────────────────────────────
    op.create_table(
        "email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("to_addr", sa.String(255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.BigInteger()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_msg", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft','pending_approval','sent','failed')",
            name="ck_eoutbox_status",
        ),
    )
    op.create_index("idx_eoutbox_status_created", "email_outbox", ["status", "created_at"])
    op.create_index("idx_eoutbox_lead", "email_outbox", ["lead_id"])

    # ── funnel_stages ─────────────────────────────────────────────────────────
    op.create_table(
        "funnel_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("exited_at", sa.DateTime(timezone=True)),
        sa.Column("agent_name", sa.String(64)),
        sa.Column("score_before", sa.SmallInteger()),
        sa.Column("score_after", sa.SmallInteger()),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "stage IN ('new','contacted','interested','proposal','negotiation','won','lost')",
            name="ck_funnel_stage",
        ),
    )
    op.create_index("idx_funnel_lead_entered", "funnel_stages", ["lead_id", "entered_at"])
    op.create_index("idx_funnel_stage_entered", "funnel_stages", ["stage", "entered_at"])

    # ── cart_items ────────────────────────────────────────────────────────────
    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(8, 2), nullable=False, server_default="1"),
        sa.Column("price_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("quantity_kg > 0", name="ck_cart_qty_positive"),
    )
    op.create_index(
        "uq_cart_session_product",
        "cart_items",
        ["session_id", "product_id"],
        unique=True,
    )
    op.create_index("idx_cart_session", "cart_items", ["session_id", "created_at"])

    # ── payments ──────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.String(255), unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="RUB"),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(64), server_default="yukassa"),
        sa.Column("provider_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "method IN ('online','on_delivery')",
            name="ck_payments_method",
        ),
        sa.CheckConstraint(
            "status IN ('pending','paid','cancelled','refunded')",
            name="ck_payments_status",
        ),
    )
    op.create_index("idx_payments_order", "payments", ["order_id"])
    op.create_index("idx_payments_status_created", "payments", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("cart_items")
    op.drop_table("funnel_stages")
    op.drop_table("email_outbox")
    op.drop_table("email_inbox")
    op.drop_index("idx_pi_message_id", table_name="price_intel")
    op.drop_index("idx_pi_source_time", table_name="price_intel")
    op.drop_index("idx_pi_product_time", table_name="price_intel")
    op.drop_table("price_intel")
    op.drop_table("ad_log")
    op.drop_index("idx_pc_active_purpose", table_name="publish_channels")
    op.drop_index("uq_pc_platform_channel_purpose", table_name="publish_channels")
    op.drop_table("publish_channels")
    op.drop_column("orders", "excel_source")
    op.drop_column("leads", "score")
