"""restore promotions module

Revision ID: 20260328_0016
Revises: 20260328_0015
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0016"
down_revision: Union[str, None] = "20260328_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promotion_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="KGS"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_promotion_packages_id", "promotion_packages", ["id"])

    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "promotion_package_id",
            sa.Integer(),
            sa.ForeignKey("promotion_packages.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("target_city", sa.String(120), nullable=True),
        sa.Column(
            "target_category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("purchased_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="KGS"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_promotions_id", "promotions", ["id"])
    op.create_index("ix_promotions_listing_id", "promotions", ["listing_id"])
    op.create_index("ix_promotions_user_id", "promotions", ["user_id"])
    op.create_index("ix_promotions_promotion_package_id", "promotions", ["promotion_package_id"])
    op.create_index("ix_promotions_target_category_id", "promotions", ["target_category_id"])
    op.create_index("ix_promotions_status", "promotions", ["status"])


def downgrade() -> None:
    op.drop_table("promotions")
    op.drop_table("promotion_packages")
