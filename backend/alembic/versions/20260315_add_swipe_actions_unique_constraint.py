"""Add unique constraint on swipe_actions(user_id, recipe_id).

Revision ID: 20260315_005
Revises: 20260315_004
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260315_005"
down_revision: str | None = "20260315_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove duplicate swipe_actions rows before adding unique constraint.
    # Keeps only the most recent row per (user_id, recipe_id).
    op.execute(
        sa.text("""
            DELETE FROM swipe_actions
            WHERE id NOT IN (
                SELECT DISTINCT ON (user_id, recipe_id) id
                FROM swipe_actions
                ORDER BY user_id, recipe_id, updated_at DESC
            )
        """)
    )
    op.create_unique_constraint(
        "uq_swipe_actions_user_recipe",
        "swipe_actions",
        ["user_id", "recipe_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_swipe_actions_user_recipe",
        "swipe_actions",
        type_="unique",
    )
