"""create favorites table

Revision ID: 20260327_0003
Revises: 20260327_0002
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0003"
down_revision: Union[str, None] = "20260327_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"),
    )

    op.create_index("ix_favorites_id", "favorites", ["id"], unique=False)
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"], unique=False)
    op.create_index("ix_favorites_listing_id", "favorites", ["listing_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_favorites_listing_id", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_index("ix_favorites_id", table_name="favorites")
    op.drop_table("favorites")
