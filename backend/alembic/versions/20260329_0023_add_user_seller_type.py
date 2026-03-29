"""add user seller type value

Revision ID: 20260329_0023
Revises: 20260329_0022
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0023"
down_revision: Union[str, None] = "20260329_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


old_seller_type_enum = sa.Enum(
    "owner",
    "company",
    name="sellertype",
    native_enum=False,
)
new_seller_type_enum = sa.Enum(
    "owner",
    "company",
    "user",
    name="sellertype",
    native_enum=False,
)


def upgrade() -> None:
    op.alter_column(
        "users",
        "seller_type",
        existing_type=old_seller_type_enum,
        type_=new_seller_type_enum,
        existing_nullable=False,
        existing_server_default="owner",
    )
    op.alter_column(
        "seller_type_change_requests",
        "requested_seller_type",
        existing_type=old_seller_type_enum,
        type_=new_seller_type_enum,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("UPDATE seller_type_change_requests SET requested_seller_type = 'owner' WHERE requested_seller_type = 'user'")
    op.execute("UPDATE users SET seller_type = 'owner' WHERE seller_type = 'user'")

    op.alter_column(
        "seller_type_change_requests",
        "requested_seller_type",
        existing_type=new_seller_type_enum,
        type_=old_seller_type_enum,
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "seller_type",
        existing_type=new_seller_type_enum,
        type_=old_seller_type_enum,
        existing_nullable=False,
        existing_server_default="owner",
    )
