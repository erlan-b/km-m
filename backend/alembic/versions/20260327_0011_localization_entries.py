"""add localization entries

Revision ID: 20260327_0011
Revises: 20260327_0010
Create Date: 2026-03-27 19:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260327_0011"
down_revision: Union[str, None] = "20260327_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "localization_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("translations", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_localization_entries_key"),
    )
    op.create_index(op.f("ix_localization_entries_id"), "localization_entries", ["id"], unique=False)
    op.create_index(op.f("ix_localization_entries_is_active"), "localization_entries", ["is_active"], unique=False)
    op.create_index(op.f("ix_localization_entries_key"), "localization_entries", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_localization_entries_key"), table_name="localization_entries")
    op.drop_index(op.f("ix_localization_entries_is_active"), table_name="localization_entries")
    op.drop_index(op.f("ix_localization_entries_id"), table_name="localization_entries")
    op.drop_table("localization_entries")