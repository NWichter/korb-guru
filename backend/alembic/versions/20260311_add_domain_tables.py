"""Add all domain tables and rebuild users with UUID PK.

Drops the old users table (int PK, name column) and recreates it with UUID PK
and Clerk identity fields. Creates all 15 additional domain tables for the
integrated backend.

Revision ID: 20260311_002
Revises: f52f8e9e1113
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260311_002"
down_revision: str | None = "f52f8e9e1113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 1. Drop old users table (int PK, no clerk_id) ---
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    # --- 2. Create users (without household_id FK to break circular dep) ---
    _ = op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clerk_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column(
            "health_streak_days", sa.Integer(), nullable=False, server_default="0"
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("clerk_id", name=op.f("uq_users_clerk_id")),
    )
    op.create_index(op.f("ix_users_clerk_id"), "users", ["clerk_id"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_household_id"), "users", ["household_id"])

    # --- 3. Create households ---
    _ = op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("invite_code", sa.String(50), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_households")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_households_created_by_users")
        ),
        sa.UniqueConstraint("invite_code", name=op.f("uq_households_invite_code")),
    )
    op.create_index(
        op.f("ix_households_invite_code"), "households", ["invite_code"], unique=True
    )

    # --- 4. Add FK: users.household_id -> households.id ---
    op.create_foreign_key(
        op.f("fk_users_household_id_households"),
        "users",
        "households",
        ["household_id"],
        ["id"],
    )

    # --- 5. Create recipes ---
    _ = op.create_table(
        "recipes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(5000), nullable=True),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("time_minutes", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipes")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_recipes_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_recipes_created_by_users")
        ),
    )
    op.create_index(op.f("ix_recipes_household_id"), "recipes", ["household_id"])
    op.create_index(op.f("ix_recipes_created_by"), "recipes", ["created_by"])

    # --- 6. Create recipe_ingredients ---
    _ = op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("quantity", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_ingredients")),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_recipe_ingredients_recipe_id_recipes"),
        ),
    )
    op.create_index(
        op.f("ix_recipe_ingredients_recipe_id"), "recipe_ingredients", ["recipe_id"]
    )

    # --- 7. Create swipe_actions ---
    _ = op.create_table(
        "swipe_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_swipe_actions")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_swipe_actions_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_swipe_actions_recipe_id_recipes"),
        ),
    )
    op.create_index(op.f("ix_swipe_actions_user_id"), "swipe_actions", ["user_id"])
    op.create_index(op.f("ix_swipe_actions_recipe_id"), "swipe_actions", ["recipe_id"])

    # --- 8. Create meal_plans ---
    _ = op.create_table(
        "meal_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("meal_slot", sa.String(20), nullable=False, server_default="dinner"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meal_plans")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_meal_plans_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name=op.f("fk_meal_plans_recipe_id_recipes")
        ),
        sa.CheckConstraint(
            "meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name=op.f("ck_meal_plans_ck_meal_plans_meal_slot"),
        ),
    )
    op.create_index(op.f("ix_meal_plans_household_id"), "meal_plans", ["household_id"])

    # --- 9. Create grocery_lists ---
    _ = op.create_table(
        "grocery_lists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column(
            "name", sa.String(200), nullable=False, server_default="Shopping List"
        ),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column(
            "estimated_total", sa.Numeric(10, 2), nullable=False, server_default="0.0"
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grocery_lists")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_grocery_lists_household_id_households"),
        ),
    )
    op.create_index(
        op.f("ix_grocery_lists_household_id"), "grocery_lists", ["household_id"]
    )

    # --- 10. Create grocery_items ---
    _ = op.create_table(
        "grocery_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grocery_list_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_name", sa.String(300), nullable=False),
        sa.Column("quantity", sa.String(100), nullable=True),
        sa.Column(
            "is_checked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grocery_items")),
        sa.ForeignKeyConstraint(
            ["grocery_list_id"],
            ["grocery_lists.id"],
            name=op.f("fk_grocery_items_grocery_list_id_grocery_lists"),
        ),
    )
    op.create_index(
        op.f("ix_grocery_items_grocery_list_id"), "grocery_items", ["grocery_list_id"]
    )

    # --- 11. Create budget_entries ---
    _ = op.create_table(
        "budget_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_entries")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_budget_entries_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["users.id"],
            name=op.f("fk_budget_entries_recorded_by_users"),
        ),
    )
    op.create_index(
        op.f("ix_budget_entries_household_id"), "budget_entries", ["household_id"]
    )
    op.create_index(
        op.f("ix_budget_entries_recorded_by"), "budget_entries", ["recorded_by"]
    )

    # --- 12. Create budget_settings ---
    _ = op.create_table(
        "budget_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column(
            "weekly_limit", sa.Numeric(10, 2), nullable=False, server_default="80.00"
        ),
        sa.Column(
            "total_savings", sa.Numeric(10, 2), nullable=False, server_default="0.00"
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_settings")),
        sa.UniqueConstraint(
            "household_id", name=op.f("uq_budget_settings_household_id")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_budget_settings_household_id_households"),
        ),
    )

    # --- 13. Create products ---
    _ = op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("retailer", sa.String(50), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("original_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("discount_pct", sa.Float(), nullable=True),
        sa.Column("category", sa.String(200), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="custom"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(op.f("ix_products_retailer"), "products", ["retailer"])
    op.create_index(op.f("ix_products_category"), "products", ["category"])

    # --- 14. Create stores ---
    _ = op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stores")),
    )

    # --- 15. Create messages ---
    _ = op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(5000), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="text"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_messages_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_messages_user_id_users")
        ),
    )
    op.create_index(op.f("ix_messages_household_id"), "messages", ["household_id"])

    # --- 16. Create notifications ---
    _ = op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False, server_default="bell"),
        sa.Column(
            "color", sa.String(50), nullable=False, server_default="bg-emerald-500"
        ),
        sa.Column(
            "is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users")
        ),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"])

    # --- 17. Create meal_polls ---
    _ = op.create_table(
        "meal_polls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meal_polls")),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_meal_polls_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name=op.f("fk_meal_polls_recipe_id_recipes")
        ),
        sa.ForeignKeyConstraint(
            ["proposed_by"], ["users.id"], name=op.f("fk_meal_polls_proposed_by_users")
        ),
    )
    op.create_index(op.f("ix_meal_polls_household_id"), "meal_polls", ["household_id"])

    # --- 18. Create poll_votes ---
    _ = op.create_table(
        "poll_votes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vote", sa.String(10), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_poll_votes")),
        sa.ForeignKeyConstraint(
            ["poll_id"],
            ["meal_polls.id"],
            name=op.f("fk_poll_votes_poll_id_meal_polls"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_poll_votes_user_id_users")
        ),
    )
    op.create_index(op.f("ix_poll_votes_poll_id"), "poll_votes", ["poll_id"])


def downgrade() -> None:
    op.drop_table("poll_votes")
    op.drop_table("meal_polls")
    op.drop_table("notifications")
    op.drop_table("messages")
    op.drop_table("stores")
    op.drop_table("products")
    op.drop_table("budget_settings")
    op.drop_table("budget_entries")
    op.drop_table("grocery_items")
    op.drop_table("grocery_lists")
    op.drop_table("meal_plans")
    op.drop_table("swipe_actions")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
    op.drop_constraint(
        op.f("fk_users_household_id_households"), "users", type_="foreignkey"
    )
    op.drop_table("households")

    # Drop new users table and recreate old one
    op.drop_table("users")
    _ = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
