import os
import subprocess
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import (  # pyright: ignore[reportMissingTypeStubs]
    PostgresContainer,
)

from src.db import get_db
from src.main import app


def _to_asyncpg_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)


@pytest_asyncio.fixture
async def migrated_async_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    sync_url = postgres_container.get_connection_url()
    env = os.environ.copy()
    env["DATABASE_URL"] = sync_url

    _ = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=True,
    )

    engine = create_async_engine(
        _to_asyncpg_url(sync_url),
        echo=False,
        poolclass=NullPool,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def migrated_db_session(
    migrated_async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=migrated_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def migrated_client(
    migrated_db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield migrated_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client

    _ = app.dependency_overrides.pop(get_db, None)


EXPECTED_TABLES = {
    "alembic_version",
    "example",
    "users",
    "households",
    "recipes",
    "recipe_ingredients",
    "swipe_actions",
    "meal_plans",
    "grocery_lists",
    "grocery_items",
    "budget_entries",
    "budget_settings",
    "products",
    "stores",
    "messages",
    "notifications",
    "meal_polls",
    "poll_votes",
}


@pytest.mark.asyncio
async def test_alembic_head_creates_all_domain_tables(
    migrated_async_engine: AsyncEngine,
    migrated_client: AsyncClient,
) -> None:
    """After alembic upgrade head, all 16 domain tables + example exist."""
    async with migrated_async_engine.connect() as conn:
        table_names = set(
            await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        )

    assert EXPECTED_TABLES.issubset(table_names), (
        f"Missing tables: {EXPECTED_TABLES - table_names}"
    )

    # Legacy /examples route still works
    response = await migrated_client.get("/examples")

    assert response.status_code == 200
    assert response.json() == []
