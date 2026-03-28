"""link payments to promotions and restore description

Revision ID: 20260328_0017
Revises: 20260328_0016
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0017"
down_revision: Union[str, None] = "20260328_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("promotion_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("promotion_package_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("description", sa.String(length=500), nullable=True))

    op.create_index("ix_payments_promotion_id", "payments", ["promotion_id"], unique=False)
    op.create_index("ix_payments_promotion_package_id", "payments", ["promotion_package_id"], unique=False)

    op.create_foreign_key(
        "fk_payments_promotion_id_promotions",
        "payments",
        "promotions",
        ["promotion_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_payments_promotion_package_id_promotion_packages",
        "payments",
        "promotion_packages",
        ["promotion_package_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_promotion_package_id_promotion_packages", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_promotion_id_promotions", "payments", type_="foreignkey")

    op.drop_index("ix_payments_promotion_package_id", table_name="payments")
    op.drop_index("ix_payments_promotion_id", table_name="payments")

    op.drop_column("payments", "description")
    op.drop_column("payments", "promotion_package_id")
    op.drop_column("payments", "promotion_id")
