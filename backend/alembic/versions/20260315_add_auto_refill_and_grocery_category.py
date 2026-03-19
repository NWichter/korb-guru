"""Add auto_refill_rules table and category column to grocery_items.

Revision ID: 20260315_001
Revises: 20260311_002
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260315_001"
down_revision: str | None = "20260311_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 1. Add category column to grocery_items ---
    op.add_column(
        "grocery_items",
        sa.Column("category", sa.String(100), nullable=False, server_default="Other"),
    )

    # --- 2. Create auto_refill_rules table ---
    op.create_table(
        "auto_refill_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("ingredient_name", sa.String(200), nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index(
        op.f("ix_auto_refill_rules_household_id"),
        "auto_refill_rules",
        ["household_id"],
    )
    op.create_unique_constraint(
        "uq_auto_refill_household_ingredient",
        "auto_refill_rules",
        ["household_id", "ingredient_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_auto_refill_household_ingredient",
        "auto_refill_rules",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_auto_refill_rules_household_id"),
        table_name="auto_refill_rules",
    )
    op.drop_table("auto_refill_rules")
    op.drop_column("grocery_items", "category")
