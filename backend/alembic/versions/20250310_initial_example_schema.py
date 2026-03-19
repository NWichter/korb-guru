"""Initial example schema (no seed; use pnpm db:seed:postgres for data).

Revision ID: 20250310_001
Revises:
Create Date: 2025-03-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20250310_001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _ = op.create_table(
        "example",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_example")),
    )


def downgrade() -> None:
    op.drop_table("example")
