"""remove promotions and localization tables

Revision ID: 20260328_0014
Revises: 20260328_0013
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260328_0014"
down_revision: Union[str, None] = "20260328_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

promotion_status_enum = sa.Enum(
    "pending",
    "active",
    "expired",
    "cancelled",
    name="promotionstatus",
)


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    columns = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    return column_name in columns


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    indexes = sa.inspect(bind).get_indexes(table_name)
    return {index["name"] for index in indexes if index.get("name")}


def _drop_index_if_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> None:
    if index_name in _index_names(bind, table_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_fk_for_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> None:
    if not _table_exists(bind, table_name):
        return

    for fk in sa.inspect(bind).get_foreign_keys(table_name):
        constrained_columns = fk.get("constrained_columns") or []
        fk_name = fk.get("name")
        if column_name in constrained_columns and fk_name:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if _column_exists(bind, "payments", "promotion_package_id"):
        if dialect == "sqlite":
            with op.batch_alter_table("payments") as batch_op:
                batch_op.drop_column("promotion_package_id")
        else:
            _drop_fk_for_column(bind, "payments", "promotion_package_id")
            _drop_index_if_exists(bind, "payments", "ix_payments_promotion_package_id")
            op.drop_column("payments", "promotion_package_id")

    if _table_exists(bind, "promotions"):
        op.drop_table("promotions")

    if _table_exists(bind, "promotion_packages"):
        op.drop_table("promotion_packages")

    if _table_exists(bind, "localization_entries"):
        op.drop_table("localization_entries")

    promotion_status_enum.drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _table_exists(bind, "promotion_packages"):
        op.create_table(
            "promotion_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("duration_days", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_promotion_packages_id", "promotion_packages", ["id"], unique=False)

    if _table_exists(bind, "payments") and not _column_exists(bind, "payments", "promotion_package_id"):
        if dialect == "sqlite":
            with op.batch_alter_table("payments") as batch_op:
                batch_op.add_column(sa.Column("promotion_package_id", sa.Integer(), nullable=True))
        else:
            op.add_column("payments", sa.Column("promotion_package_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                None,
                "payments",
                "promotion_packages",
                ["promotion_package_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if "ix_payments_promotion_package_id" not in _index_names(bind, "payments"):
            op.create_index("ix_payments_promotion_package_id", "payments", ["promotion_package_id"], unique=False)

    if not _table_exists(bind, "promotions"):
        op.create_table(
            "promotions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "promotion_package_id",
                sa.Integer(),
                sa.ForeignKey("promotion_packages.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("promotion_type", sa.String(length=50), nullable=False),
            sa.Column("target_city", sa.String(length=120), nullable=True),
            sa.Column(
                "target_category_id",
                sa.Integer(),
                sa.ForeignKey("categories.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("starts_at", sa.DateTime(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=False),
            sa.Column("status", promotion_status_enum, nullable=False),
            sa.Column("purchased_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

        op.create_index("ix_promotions_id", "promotions", ["id"], unique=False)
        op.create_index("ix_promotions_listing_id", "promotions", ["listing_id"], unique=False)
        op.create_index("ix_promotions_user_id", "promotions", ["user_id"], unique=False)
        op.create_index("ix_promotions_promotion_package_id", "promotions", ["promotion_package_id"], unique=False)
        op.create_index("ix_promotions_target_category_id", "promotions", ["target_category_id"], unique=False)
        op.create_index("ix_promotions_status", "promotions", ["status"], unique=False)

    if not _table_exists(bind, "localization_entries"):
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
        op.create_index("ix_localization_entries_id", "localization_entries", ["id"], unique=False)
        op.create_index("ix_localization_entries_is_active", "localization_entries", ["is_active"], unique=False)
        op.create_index("ix_localization_entries_key", "localization_entries", ["key"], unique=True)
