"""add user presence and verification fields

Revision ID: 20260328_0019
Revises: 20260328_0018
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0019"
down_revision: Union[str, None] = "20260328_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


seller_type_enum = sa.Enum(
    "owner",
    "company",
    name="sellertype",
    native_enum=False,
)
verification_status_enum = sa.Enum(
    "unverified",
    "pending",
    "verified",
    "rejected",
    name="verificationstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "seller_type",
            seller_type_enum,
            nullable=False,
            server_default="owner",
        ),
    )
    op.add_column("users", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "verification_status",
            verification_status_enum,
            nullable=False,
            server_default="unverified",
        ),
    )
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_column("users", "verification_status")
    op.drop_column("users", "company_name")
    op.drop_column("users", "seller_type")
    op.drop_column("users", "last_seen_at")
