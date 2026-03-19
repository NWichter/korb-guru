"""Add ean, allergens, nutriscore, nutritional_info to products.

Revision ID: 20260317_002
Revises: 20260317_001
Create Date: 2026-03-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260317_002"
down_revision: str | None = "20260317_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("ean", sa.String(20), nullable=True))
    op.add_column("products", sa.Column("allergens", sa.String(500), nullable=True))
    op.add_column("products", sa.Column("nutriscore", sa.String(5), nullable=True))
    op.add_column("products", sa.Column("nutritional_info", sa.Text(), nullable=True))
    op.create_index("ix_products_ean", "products", ["ean"])


def downgrade() -> None:
    op.drop_index("ix_products_ean", table_name="products")
    op.drop_column("products", "nutritional_info")
    op.drop_column("products", "nutriscore")
    op.drop_column("products", "allergens")
    op.drop_column("products", "ean")
