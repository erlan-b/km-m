"""remove category display_order

Revision ID: 20260328_0012
Revises: 20260327_0011
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0012"
down_revision: Union[str, None] = "20260327_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("categories")}
    if "display_order" in columns:
        op.drop_column("categories", "display_order")


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("categories")}
    if "display_order" not in columns:
        op.add_column(
            "categories",
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        )
