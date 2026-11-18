"""Initial schema: all tables

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("aliases", JSONB, server_default=sa.text("'[]'")),
        sa.Column("category", sa.String(50)),
        sa.Column("unit", sa.String(10), server_default=sa.text("'кг'")),
        sa.Column("season_note", sa.String(200)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_products_category", "products", ["category"])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("telegram", sa.String(100)),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(100)),
        sa.Column("region", sa.String(100)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(50)),
        sa.Column("telegram", sa.String(100)),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(100)),
        sa.Column("city", sa.String(100)),
        sa.Column("min_order_kg", sa.Numeric(8, 2)),
        sa.Column("discount_pct", sa.Numeric(4, 2), server_default="0"),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("source", sa.String(50), server_default=sa.text("'manual'")),
        sa.Column("lead_status", sa.String(30), server_default=sa.text("'new'")),
        sa.Column("address", sa.String(300)),
        sa.Column("website", sa.String(200)),
        sa.Column("last_contact_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "supplier_prices",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id")),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")),
        sa.Column("price_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("source_url", sa.String(500)),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime),
        sa.Column("raw_name", sa.String(200)),
    )
    op.create_index("idx_sp_product_time", "supplier_prices", ["product_id", "recorded_at"])
    op.create_index("idx_sp_supplier_time", "supplier_prices", ["supplier_id", "recorded_at"])
    op.create_index("idx_sp_recorded", "supplier_prices", ["recorded_at"])

    op.create_table(
        "my_prices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")),
        sa.Column("price_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("valid_from", sa.DateTime, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_mp_product", "my_prices", ["product_id", "valid_from"])

    op.create_table(
        "style_examples",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("platform", sa.String(20)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_original", sa.Boolean, server_default="false"),
        sa.Column("feedback_score", sa.SmallInteger, server_default="0"),
        sa.Column("generation_params", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_memory",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "preis_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_path", sa.String(500)),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("positions_count", sa.Integer),
        sa.Column("checksum", sa.String(64)),
    )


def downgrade() -> None:
    op.drop_table("preis_versions")
    op.drop_table("agent_memory")
    op.drop_table("style_examples")
    op.drop_index("idx_mp_product", "my_prices")
    op.drop_table("my_prices")
    op.drop_index("idx_sp_recorded", "supplier_prices")
    op.drop_index("idx_sp_supplier_time", "supplier_prices")
    op.drop_index("idx_sp_product_time", "supplier_prices")
    op.drop_table("supplier_prices")
    op.drop_table("clients")
    op.drop_table("suppliers")
    op.drop_index("idx_products_category", "products")
    op.drop_table("products")
