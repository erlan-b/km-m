"""rename premium fields to subscription

Revision ID: 20260328_0013
Revises: 20260328_0012
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0013"
down_revision: Union[str, None] = "20260328_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_column(
    bind: sa.engine.Connection,
    table_name: str,
    old_name: str,
    new_name: str,
    existing_type: sa.types.TypeEngine,
    existing_nullable: bool,
) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                old_name,
                new_column_name=new_name,
                existing_type=existing_type,
                existing_nullable=existing_nullable,
            )
    else:
        op.alter_column(
            table_name,
            old_name,
            new_column_name=new_name,
            existing_type=existing_type,
            existing_nullable=existing_nullable,
        )


def upgrade() -> None:
    bind = op.get_bind()

    listing_columns = {column["name"] for column in sa.inspect(bind).get_columns("listings")}
    if "is_premium" in listing_columns and "is_subscription" not in listing_columns:
        _rename_column(
            bind,
            "listings",
            "is_premium",
            "is_subscription",
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )
    if "premium_expires_at" in listing_columns and "subscription_expires_at" not in listing_columns:
        _rename_column(
            bind,
            "listings",
            "premium_expires_at",
            "subscription_expires_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )

    promotion_columns = {column["name"] for column in sa.inspect(bind).get_columns("promotions")}
    if "promotion_type" in promotion_columns:
        op.execute(
            sa.text(
                "UPDATE promotions "
                "SET promotion_type = 'subscription' "
                "WHERE promotion_type = 'premium'"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    promotion_columns = {column["name"] for column in sa.inspect(bind).get_columns("promotions")}
    if "promotion_type" in promotion_columns:
        op.execute(
            sa.text(
                "UPDATE promotions "
                "SET promotion_type = 'premium' "
                "WHERE promotion_type = 'subscription'"
            )
        )

    listing_columns = {column["name"] for column in sa.inspect(bind).get_columns("listings")}
    if "is_subscription" in listing_columns and "is_premium" not in listing_columns:
        _rename_column(
            bind,
            "listings",
            "is_subscription",
            "is_premium",
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )
    if "subscription_expires_at" in listing_columns and "premium_expires_at" not in listing_columns:
        _rename_column(
            bind,
            "listings",
            "subscription_expires_at",
            "premium_expires_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
