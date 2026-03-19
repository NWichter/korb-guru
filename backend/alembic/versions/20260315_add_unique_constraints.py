"""Add unique constraint on poll_votes(poll_id, user_id).

Revision ID: 20260315_002
Revises: 20260315_001
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260315_002"
down_revision: str | None = "20260315_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove duplicate poll_votes rows before adding unique constraint.
    # Keeps only the most recent row per (poll_id, user_id).
    op.execute(
        sa.text("""
            DELETE FROM poll_votes
            WHERE id NOT IN (
                SELECT DISTINCT ON (poll_id, user_id) id
                FROM poll_votes
                ORDER BY poll_id, user_id, updated_at DESC
            )
        """)
    )
    op.create_unique_constraint(
        "uq_poll_votes_poll_user",
        "poll_votes",
        ["poll_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_poll_votes_poll_user",
        "poll_votes",
        type_="unique",
    )
