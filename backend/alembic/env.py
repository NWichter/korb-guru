"""
Alembic migration environment. Reads DATABASE_URL from environment.
Run from backend/: uv run alembic upgrade head.

When the API has SQLAlchemy Base/metadata: set target_metadata = Base.metadata below
and add a naming_convention on Base for stable autogenerate (see Alembic naming docs).
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from alembic import context

# Import ALL models so they register on Base.metadata for autogenerate
from src.models import (  # noqa: F401
    Base,
    BudgetEntry,
    BudgetSettings,
    GroceryItem,
    GroceryList,
    Household,
    MealPlan,
    MealPoll,
    Message,
    Notification,
    PollVote,
    Product,
    Recipe,
    RecipeIngredient,
    Store,
    SwipeAction,
    User,
)

# Load .env: first try current directory, then repo root (relative to this file).

# Using __file__ ensures resolution works when running from backend/.
env_paths = (
    os.path.join(os.getcwd(), ".env"),  # When running from repo root
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),  # backend/../.env
)

for path in env_paths:
    if os.path.isfile(path):
        load_dotenv(path)

        break


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Ensure psycopg2 driver for postgres(ql):// URLs (support both schemes)
    if database_url.startswith("postgres://") and "postgres+" not in database_url:
        database_url = "postgresql+psycopg2://" + database_url.split("://", 1)[1]
    elif database_url.startswith("postgresql://") and "postgresql+" not in database_url:
        database_url = "postgresql+psycopg2://" + database_url.split("://", 1)[1]
    config.set_main_option("sqlalchemy.url", database_url)

# Set metadata for autogenerate support.
# Import models here (or via src.models) so they register on Base.metadata.
# When adding models (e.g., User), ensure they're imported before autogenerate runs.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url", ""),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
