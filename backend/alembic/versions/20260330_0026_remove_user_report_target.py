"""remove user report target type

Revision ID: 20260330_0026
Revises: 20260330_0025
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0026"
down_revision: Union[str, None] = "20260330_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


report_target_type_enum_old = sa.Enum("listing", "user", "message", name="reporttargettype")
report_target_type_enum_new = sa.Enum("listing", "message", name="reporttargettype")


def upgrade() -> None:
    op.execute("DELETE FROM reports WHERE target_type = 'user'")
    op.alter_column(
        "reports",
        "target_type",
        existing_type=report_target_type_enum_old,
        type_=report_target_type_enum_new,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "reports",
        "target_type",
        existing_type=report_target_type_enum_new,
        type_=report_target_type_enum_old,
        existing_nullable=False,
    )