"""add user profile fields

Revision ID: 20260328_0015
Revises: 20260328_0014
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0015"
down_revision: Union[str, None] = "20260328_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("profile_image_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(1000), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(120), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "city")
    op.drop_column("users", "bio")
    op.drop_column("users", "profile_image_url")
    op.drop_column("users", "phone")
