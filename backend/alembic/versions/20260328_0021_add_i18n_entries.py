"""add i18n entries table

Revision ID: 20260328_0021
Revises: 20260328_0020
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0021"
down_revision: Union[str, None] = "20260328_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    indexes = sa.inspect(bind).get_indexes(table_name)
    return {index["name"] for index in indexes if index.get("name")}


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "i18n_entries"):
        op.create_table(
            "i18n_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("page_key", sa.String(length=120), nullable=False),
            sa.Column("text_key", sa.String(length=180), nullable=False),
            sa.Column("language", sa.String(length=16), nullable=False),
            sa.Column("text_value", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("page_key", "text_key", "language", name="uq_i18n_entries_page_text_language"),
        )

    index_names = _index_names(bind, "i18n_entries")
    if "ix_i18n_entries_id" not in index_names:
        op.create_index("ix_i18n_entries_id", "i18n_entries", ["id"], unique=False)
    if "ix_i18n_entries_page_key" not in index_names:
        op.create_index("ix_i18n_entries_page_key", "i18n_entries", ["page_key"], unique=False)
    if "ix_i18n_entries_text_key" not in index_names:
        op.create_index("ix_i18n_entries_text_key", "i18n_entries", ["text_key"], unique=False)
    if "ix_i18n_entries_language" not in index_names:
        op.create_index("ix_i18n_entries_language", "i18n_entries", ["language"], unique=False)
    if "ix_i18n_entries_is_active" not in index_names:
        op.create_index("ix_i18n_entries_is_active", "i18n_entries", ["is_active"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "i18n_entries"):
        return

    index_names = _index_names(bind, "i18n_entries")
    if "ix_i18n_entries_is_active" in index_names:
        op.drop_index("ix_i18n_entries_is_active", table_name="i18n_entries")
    if "ix_i18n_entries_language" in index_names:
        op.drop_index("ix_i18n_entries_language", table_name="i18n_entries")
    if "ix_i18n_entries_text_key" in index_names:
        op.drop_index("ix_i18n_entries_text_key", table_name="i18n_entries")
    if "ix_i18n_entries_page_key" in index_names:
        op.drop_index("ix_i18n_entries_page_key", table_name="i18n_entries")
    if "ix_i18n_entries_id" in index_names:
        op.drop_index("ix_i18n_entries_id", table_name="i18n_entries")

    op.drop_table("i18n_entries")