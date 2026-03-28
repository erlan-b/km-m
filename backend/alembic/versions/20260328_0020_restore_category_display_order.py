"""restore category display_order

Revision ID: 20260328_0020
Revises: 20260328_0019
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0020"
down_revision: Union[str, None] = "20260328_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("categories")}

    if "display_order" not in columns:
        op.add_column(
            "categories",
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("categories")}
    if "ix_categories_display_order" not in indexes:
        op.create_index("ix_categories_display_order", "categories", ["display_order"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {index["name"] for index in inspector.get_indexes("categories")}
    if "ix_categories_display_order" in indexes:
        op.drop_index("ix_categories_display_order", table_name="categories")

    columns = {column["name"] for column in inspector.get_columns("categories")}
    if "display_order" in columns:
        op.drop_column("categories", "display_order")
