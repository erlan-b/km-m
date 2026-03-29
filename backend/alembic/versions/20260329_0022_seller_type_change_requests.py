"""add seller type change requests with documents

Revision ID: 20260329_0022
Revises: 20260328_0021
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0022"
down_revision: Union[str, None] = "20260328_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


seller_type_enum = sa.Enum(
    "owner",
    "company",
    name="sellertype",
    native_enum=False,
)
seller_type_change_status_enum = sa.Enum(
    "pending",
    "approved",
    "rejected",
    name="sellertypechangerequeststatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "seller_type_change_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_seller_type", seller_type_enum, nullable=False),
        sa.Column("requested_company_name", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", seller_type_change_status_enum, nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "seller_type_change_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("seller_type_change_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index(
        "ix_seller_type_change_requests_id",
        "seller_type_change_requests",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_requests_user_id",
        "seller_type_change_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_requests_requested_seller_type",
        "seller_type_change_requests",
        ["requested_seller_type"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_requests_status",
        "seller_type_change_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_requests_reviewed_by_admin_id",
        "seller_type_change_requests",
        ["reviewed_by_admin_id"],
        unique=False,
    )

    op.create_index(
        "ix_seller_type_change_documents_id",
        "seller_type_change_documents",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_documents_request_id",
        "seller_type_change_documents",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_seller_type_change_documents_mime_type",
        "seller_type_change_documents",
        ["mime_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_seller_type_change_documents_mime_type", table_name="seller_type_change_documents")
    op.drop_index("ix_seller_type_change_documents_request_id", table_name="seller_type_change_documents")
    op.drop_index("ix_seller_type_change_documents_id", table_name="seller_type_change_documents")

    op.drop_index("ix_seller_type_change_requests_reviewed_by_admin_id", table_name="seller_type_change_requests")
    op.drop_index("ix_seller_type_change_requests_status", table_name="seller_type_change_requests")
    op.drop_index("ix_seller_type_change_requests_requested_seller_type", table_name="seller_type_change_requests")
    op.drop_index("ix_seller_type_change_requests_user_id", table_name="seller_type_change_requests")
    op.drop_index("ix_seller_type_change_requests_id", table_name="seller_type_change_requests")

    op.drop_table("seller_type_change_documents")
    op.drop_table("seller_type_change_requests")

    seller_type_change_status_enum.drop(op.get_bind(), checkfirst=True)
