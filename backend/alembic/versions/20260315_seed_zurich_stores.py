"""Seed Zürich-area stores.

Revision ID: 20260315_003
Revises: 20260315_002

NOTE: Seeded stores have no google_place_id. If Google Maps ingest runs later,
it will create duplicate store rows for the same physical locations because
it matches on google_place_id (unique constraint). This is a known limitation.
TODO: Back-fill google_place_id for seeded stores, or add a dedup step
in the Google Maps ingest pipeline that matches on name+address proximity.
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision: str = "20260315_003"
down_revision: str | None = "20260315_002"
branch_labels: tuple | None = None
depends_on: tuple | None = None

ZURICH_STORES = [
    {
        "name": "Migros City Zürich",
        "brand": "migros",
        "latitude": 47.3744,
        "longitude": 8.5389,
        "address": "Löwenstrasse 35, 8001 Zürich",
    },
    {
        "name": "Migros Stadelhofen",
        "brand": "migros",
        "latitude": 47.3667,
        "longitude": 8.5486,
        "address": "Stadelhoferstrasse 10, 8001 Zürich",
    },
    {
        "name": "Migros Limmatplatz",
        "brand": "migros",
        "latitude": 47.3842,
        "longitude": 8.5319,
        "address": "Limmatstrasse 152, 8005 Zürich",
    },
    {
        "name": "Migros Oerlikon",
        "brand": "migros",
        "latitude": 47.4111,
        "longitude": 8.5444,
        "address": "Marktplatz Oerlikon, 8050 Zürich",
    },
    {
        "name": "Migros Altstetten",
        "brand": "migros",
        "latitude": 47.3911,
        "longitude": 8.4886,
        "address": "Badenerstrasse 571, 8048 Zürich",
    },
    {
        "name": "Coop City Zürich",
        "brand": "coop",
        "latitude": 47.3726,
        "longitude": 8.5387,
        "address": "Bahnhofstrasse 57, 8001 Zürich",
    },
    {
        "name": "Coop Bellevue",
        "brand": "coop",
        "latitude": 47.3664,
        "longitude": 8.5454,
        "address": "Theaterstrasse 12, 8001 Zürich",
    },
    {
        "name": "Coop Wipkingen",
        "brand": "coop",
        "latitude": 47.3936,
        "longitude": 8.5228,
        "address": "Röschibachstrasse 20, 8037 Zürich",
    },
    {
        "name": "Coop Oerlikon",
        "brand": "coop",
        "latitude": 47.4103,
        "longitude": 8.5450,
        "address": "Franklinstrasse 20, 8050 Zürich",
    },
    {
        "name": "Coop Wiedikon",
        "brand": "coop",
        "latitude": 47.3647,
        "longitude": 8.5208,
        "address": "Birmensdorferstrasse 320, 8055 Zürich",
    },
    {
        "name": "Aldi Suisse Zürich Sihlcity",
        "brand": "aldi",
        "latitude": 47.3561,
        "longitude": 8.5261,
        "address": "Kalanderplatz 1, 8045 Zürich",
    },
    {
        "name": "Aldi Suisse Zürich Oerlikon",
        "brand": "aldi",
        "latitude": 47.4125,
        "longitude": 8.5483,
        "address": "Thurgauerstrasse 34, 8050 Zürich",
    },
    {
        "name": "Aldi Suisse Zürich Altstetten",
        "brand": "aldi",
        "latitude": 47.3903,
        "longitude": 8.4839,
        "address": "Hohlstrasse 560, 8048 Zürich",
    },
    {
        "name": "Aldi Suisse Affoltern",
        "brand": "aldi",
        "latitude": 47.4217,
        "longitude": 8.5125,
        "address": "Wehntalerstrasse 540, 8046 Zürich",
    },
    {
        "name": "Lidl Zürich HB",
        "brand": "lidl",
        "latitude": 47.3782,
        "longitude": 8.5392,
        "address": "Europaallee 36, 8004 Zürich",
    },
    {
        "name": "Lidl Zürich Altstetten",
        "brand": "lidl",
        "latitude": 47.3889,
        "longitude": 8.4869,
        "address": "Badenerstrasse 549, 8048 Zürich",
    },
    {
        "name": "Lidl Zürich Oerlikon",
        "brand": "lidl",
        "latitude": 47.4097,
        "longitude": 8.5467,
        "address": "Schaffhauserstrasse 355, 8050 Zürich",
    },
    {
        "name": "Lidl Schlieren",
        "brand": "lidl",
        "latitude": 47.3967,
        "longitude": 8.4500,
        "address": "Engstringerstrasse 2, 8952 Schlieren",
    },
    {
        "name": "Denner Zürich Langstrasse",
        "brand": "denner",
        "latitude": 47.3778,
        "longitude": 8.5278,
        "address": "Langstrasse 120, 8004 Zürich",
    },
    {
        "name": "Denner Zürich Wiedikon",
        "brand": "denner",
        "latitude": 47.3650,
        "longitude": 8.5192,
        "address": "Birmensdorferstrasse 290, 8055 Zürich",
    },
    {
        "name": "Denner Zürich Wipkingen",
        "brand": "denner",
        "latitude": 47.3950,
        "longitude": 8.5208,
        "address": "Hönggerstrasse 40, 8037 Zürich",
    },
    {
        "name": "Denner Zürich Schwamendingen",
        "brand": "denner",
        "latitude": 47.4069,
        "longitude": 8.5681,
        "address": "Winterthurerstrasse 531, 8051 Zürich",
    },
    {
        "name": "Denner Zürich Seebach",
        "brand": "denner",
        "latitude": 47.4222,
        "longitude": 8.5444,
        "address": "Schaffhauserstrasse 550, 8052 Zürich",
    },
]


def upgrade() -> None:
    stores_table = sa.table(
        "stores",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("brand", sa.String),
        sa.column("latitude", sa.Float),
        sa.column("longitude", sa.Float),
        sa.column("address", sa.String),
    )
    conn = op.get_bind()
    for store in ZURICH_STORES:
        exists = conn.execute(
            sa.text("SELECT 1 FROM stores WHERE name = :name"),
            {"name": store["name"]},
        ).scalar()
        if not exists:
            conn.execute(stores_table.insert().values(id=uuid.uuid4(), **store))


def downgrade() -> None:
    # Only delete the exact seeded stores by matching on name, brand, and address
    conn = op.get_bind()
    for store in ZURICH_STORES:
        conn.execute(
            sa.text(
                "DELETE FROM stores WHERE name = :name "
                "AND brand = :brand AND address = :address"
            ),
            {
                "name": store["name"],
                "brand": store["brand"],
                "address": store["address"],
            },
        )
