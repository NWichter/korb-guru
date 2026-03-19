from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import (
    PostgresContainer,  # pyright: ignore[reportMissingTypeStubs]
)

from src.models.base import Base

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    container = PostgresContainer("postgres:16-alpine")
    _ = container.start()
    yield container
    container.stop()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://", 1
    )
    engine = create_async_engine(url, echo=False, poolclass=NullPool)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def create_tables(async_engine: AsyncEngine) -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def db_session(
    async_engine: AsyncEngine, create_tables: None
) -> AsyncGenerator[AsyncSession, None]:
    _ = create_tables

    async with async_engine.connect() as conn:
        async with conn.begin() as transaction:
            session_factory = async_sessionmaker(
                bind=conn,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async with session_factory() as session:
                try:
                    yield session
                finally:
                    if transaction.is_active:
                        await transaction.rollback()
