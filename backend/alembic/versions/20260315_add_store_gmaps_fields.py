"""Add Google Maps fields to stores table.

Revision ID: 20260315_004
Revises: 20260315_003
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260315_004"
down_revision: str | None = "20260315_003"
branch_labels: tuple | None = None
depends_on: tuple | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("google_place_id", sa.String(100), nullable=True))
    op.add_column("stores", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("stores", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("stores", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column("stores", sa.Column("opening_hours", sa.Text(), nullable=True))

    op.create_index("ix_stores_brand", "stores", ["brand"])
    # TODO: Seeded stores without google_place_id will have NULL, which passes
    # the unique constraint. When Google Places data is backfilled, ensure
    # existing seeded stores are updated (not duplicated) by matching on
    # brand+name+address before inserting new rows.
    op.create_unique_constraint(
        "uq_stores_google_place_id", "stores", ["google_place_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_stores_google_place_id", "stores", type_="unique")
    op.drop_index("ix_stores_brand", table_name="stores")

    op.drop_column("stores", "opening_hours")
    op.drop_column("stores", "rating")
    op.drop_column("stores", "website")
    op.drop_column("stores", "phone")
    op.drop_column("stores", "google_place_id")
