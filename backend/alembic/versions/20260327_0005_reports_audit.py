"""create reports and admin audit logs

Revision ID: 20260327_0005
Revises: 20260327_0004
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0005"
down_revision: Union[str, None] = "20260327_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

report_target_type_enum = sa.Enum("listing", "user", name="reporttargettype")
report_status_enum = sa.Enum("open", "resolved", "dismissed", name="reportstatus")


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", report_target_type_enum, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=50), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("status", report_status_enum, nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_reports_id", "reports", ["id"], unique=False)
    op.create_index("ix_reports_reporter_user_id", "reports", ["reporter_user_id"], unique=False)
    op.create_index("ix_reports_target_type", "reports", ["target_type"], unique=False)
    op.create_index("ix_reports_target_id", "reports", ["target_id"], unique=False)
    op.create_index("ix_reports_reason_code", "reports", ["reason_code"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)
    op.create_index("ix_reports_reviewed_by_admin_id", "reports", ["reviewed_by_admin_id"], unique=False)

    op.create_index("ix_admin_audit_logs_id", "admin_audit_logs", ["id"], unique=False)
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"], unique=False)
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"], unique=False)
    op.create_index("ix_admin_audit_logs_target_type", "admin_audit_logs", ["target_type"], unique=False)
    op.create_index("ix_admin_audit_logs_target_id", "admin_audit_logs", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_target_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_type", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_admin_user_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_id", table_name="admin_audit_logs")

    op.drop_index("ix_reports_reviewed_by_admin_id", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_reason_code", table_name="reports")
    op.drop_index("ix_reports_target_id", table_name="reports")
    op.drop_index("ix_reports_target_type", table_name="reports")
    op.drop_index("ix_reports_reporter_user_id", table_name="reports")
    op.drop_index("ix_reports_id", table_name="reports")

    op.drop_table("admin_audit_logs")
    op.drop_table("reports")

    report_status_enum.drop(op.get_bind(), checkfirst=True)
    report_target_type_enum.drop(op.get_bind(), checkfirst=True)
