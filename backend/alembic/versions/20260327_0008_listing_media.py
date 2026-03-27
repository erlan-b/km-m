"""create listing media table

Revision ID: 20260327_0008
Revises: 20260327_0007
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0008"
down_revision: Union[str, None] = "20260327_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_listing_media_id", "listing_media", ["id"], unique=False)
    op.create_index("ix_listing_media_listing_id", "listing_media", ["listing_id"], unique=False)
    op.create_index("ix_listing_media_mime_type", "listing_media", ["mime_type"], unique=False)
    op.create_index("ix_listing_media_sort_order", "listing_media", ["sort_order"], unique=False)
    op.create_index("ix_listing_media_is_primary", "listing_media", ["is_primary"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_media_is_primary", table_name="listing_media")
    op.drop_index("ix_listing_media_sort_order", table_name="listing_media")
    op.drop_index("ix_listing_media_mime_type", table_name="listing_media")
    op.drop_index("ix_listing_media_listing_id", table_name="listing_media")
    op.drop_index("ix_listing_media_id", table_name="listing_media")
    op.drop_table("listing_media")
