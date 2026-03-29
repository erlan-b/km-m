"""remove report attachments table

Revision ID: 20260330_0025
Revises: 20260329_0024
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0025"
down_revision: Union[str, None] = "20260329_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("report_attachments")


def downgrade() -> None:
    op.create_table(
        "report_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_report_attachments_id", "report_attachments", ["id"], unique=False)
    op.create_index("ix_report_attachments_report_id", "report_attachments", ["report_id"], unique=False)
    op.create_index("ix_report_attachments_mime_type", "report_attachments", ["mime_type"], unique=False)
