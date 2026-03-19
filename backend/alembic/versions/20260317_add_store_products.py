"""Add store_products table for per-store inventory.

Revision ID: 20260317_001
Revises: 20260315_005
Create Date: 2026-03-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260317_001"
down_revision: str | None = "20260315_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("local_price", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "in_stock", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_store_products"),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_store_products_store_id_stores"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_store_products_product_id_products",
        ),
        sa.UniqueConstraint(
            "store_id", "product_id", name="uq_store_products_store_product"
        ),
    )
    op.create_index("ix_store_products_store_id", "store_products", ["store_id"])
    op.create_index("ix_store_products_product_id", "store_products", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_store_products_product_id", table_name="store_products")
    op.drop_index("ix_store_products_store_id", table_name="store_products")
    op.drop_table("store_products")
