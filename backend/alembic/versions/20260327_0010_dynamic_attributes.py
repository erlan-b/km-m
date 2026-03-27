"""add dynamic attributes support to categories and listings

Revision ID: 20260327_0010
Revises: 20260327_0009
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0010"
down_revision: Union[str, None] = "20260327_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("attributes_schema", sa.JSON(), nullable=True))
    op.add_column("listings", sa.Column("dynamic_attributes", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "dynamic_attributes")
    op.drop_column("categories", "attributes_schema")
