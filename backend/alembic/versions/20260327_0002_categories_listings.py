"""create categories and listings tables

Revision ID: 20260327_0002
Revises: 20260327_0001
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0002"
down_revision: Union[str, None] = "20260327_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

transaction_type_enum = sa.Enum("sale", "rent_long", "rent_daily", name="transactiontype")
listing_status_enum = sa.Enum(
    "draft",
    "pending_review",
    "published",
    "rejected",
    "archived",
    "inactive",
    "sold",
    name="listingstatus",
)


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_type", transaction_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("address_line", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("map_address_label", sa.String(length=255), nullable=True),
        sa.Column("status", listing_status_enum, nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("favorite_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("premium_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_categories_id", "categories", ["id"], unique=False)
    op.create_index("ix_listings_id", "listings", ["id"], unique=False)
    op.create_index("ix_listings_owner_id", "listings", ["owner_id"], unique=False)
    op.create_index("ix_listings_category_id", "listings", ["category_id"], unique=False)
    op.create_index("ix_listings_city", "listings", ["city"], unique=False)
    op.create_index("ix_listings_status", "listings", ["status"], unique=False)
    op.create_index("ix_listings_created_at", "listings", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listings_created_at", table_name="listings")
    op.drop_index("ix_listings_status", table_name="listings")
    op.drop_index("ix_listings_city", table_name="listings")
    op.drop_index("ix_listings_category_id", table_name="listings")
    op.drop_index("ix_listings_owner_id", table_name="listings")
    op.drop_index("ix_listings_id", table_name="listings")
    op.drop_index("ix_categories_id", table_name="categories")
    op.drop_table("listings")
    op.drop_table("categories")
    listing_status_enum.drop(op.get_bind(), checkfirst=True)
    transaction_type_enum.drop(op.get_bind(), checkfirst=True)
