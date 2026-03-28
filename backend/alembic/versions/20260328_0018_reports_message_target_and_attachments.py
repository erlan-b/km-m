"""add message-target report support and report attachments

Revision ID: 20260328_0018
Revises: 20260328_0017
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0018"
down_revision: Union[str, None] = "20260328_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

report_target_type_enum_old = sa.Enum("listing", "user", name="reporttargettype")
report_target_type_enum_new = sa.Enum("listing", "user", "message", name="reporttargettype")


def upgrade() -> None:
    op.alter_column(
        "reports",
        "target_type",
        existing_type=report_target_type_enum_old,
        type_=report_target_type_enum_new,
        existing_nullable=False,
    )

    op.add_column("reports", sa.Column("target_conversation_id", sa.Integer(), nullable=True))
    op.create_index("ix_reports_target_conversation_id", "reports", ["target_conversation_id"], unique=False)
    op.create_foreign_key(
        "fk_reports_target_conversation_id_conversations",
        "reports",
        "conversations",
        ["target_conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )

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


def downgrade() -> None:
    op.drop_index("ix_report_attachments_mime_type", table_name="report_attachments")
    op.drop_index("ix_report_attachments_report_id", table_name="report_attachments")
    op.drop_index("ix_report_attachments_id", table_name="report_attachments")
    op.drop_table("report_attachments")

    op.drop_constraint("fk_reports_target_conversation_id_conversations", "reports", type_="foreignkey")
    op.drop_index("ix_reports_target_conversation_id", table_name="reports")
    op.drop_column("reports", "target_conversation_id")

    op.execute("DELETE FROM reports WHERE target_type = 'message'")
    op.alter_column(
        "reports",
        "target_type",
        existing_type=report_target_type_enum_new,
        type_=report_target_type_enum_old,
        existing_nullable=False,
    )
