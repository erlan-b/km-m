"""create payments and promotions tables

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0004"
down_revision: Union[str, None] = "20260327_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

payment_status_enum = sa.Enum(
    "pending",
    "successful",
    "failed",
    "cancelled",
    "refunded",
    name="paymentstatus",
)
promotion_status_enum = sa.Enum(
    "pending",
    "active",
    "expired",
    "cancelled",
    name="promotionstatus",
)


def upgrade() -> None:
    op.create_table(
        "promotion_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "promotion_package_id",
            sa.Integer(),
            sa.ForeignKey("promotion_packages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("status", payment_status_enum, nullable=False),
        sa.Column("payment_provider", sa.String(length=50), nullable=False),
        sa.Column("provider_reference", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )

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
        sa.Column("promotion_type", sa.String(length=50), nullable=False),
        sa.Column("target_city", sa.String(length=120), nullable=True),
        sa.Column(
            "target_category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", promotion_status_enum, nullable=False),
        sa.Column("purchased_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_promotion_packages_id", "promotion_packages", ["id"], unique=False)

    op.create_index("ix_payments_id", "payments", ["id"], unique=False)
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_listing_id", "payments", ["listing_id"], unique=False)
    op.create_index("ix_payments_promotion_package_id", "payments", ["promotion_package_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)

    op.create_index("ix_promotions_id", "promotions", ["id"], unique=False)
    op.create_index("ix_promotions_listing_id", "promotions", ["listing_id"], unique=False)
    op.create_index("ix_promotions_user_id", "promotions", ["user_id"], unique=False)
    op.create_index("ix_promotions_promotion_package_id", "promotions", ["promotion_package_id"], unique=False)
    op.create_index("ix_promotions_target_category_id", "promotions", ["target_category_id"], unique=False)
    op.create_index("ix_promotions_status", "promotions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_promotions_status", table_name="promotions")
    op.drop_index("ix_promotions_target_category_id", table_name="promotions")
    op.drop_index("ix_promotions_promotion_package_id", table_name="promotions")
    op.drop_index("ix_promotions_user_id", table_name="promotions")
    op.drop_index("ix_promotions_listing_id", table_name="promotions")
    op.drop_index("ix_promotions_id", table_name="promotions")

    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_promotion_package_id", table_name="payments")
    op.drop_index("ix_payments_listing_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_id", table_name="payments")

    op.drop_index("ix_promotion_packages_id", table_name="promotion_packages")

    op.drop_table("promotions")
    op.drop_table("payments")
    op.drop_table("promotion_packages")

    promotion_status_enum.drop(op.get_bind(), checkfirst=True)
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
