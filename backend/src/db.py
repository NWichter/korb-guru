"""
Async SQLAlchemy engine for runtime DB access.

Uses DATABASE_URL from environment and asyncpg driver for async operations.
For migrations and schema, see alembic/; this module is for runtime queries only.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    pass

_engine: AsyncEngine | None = None


def _normalize_url(url: str) -> str:
    """
    Normalize DATABASE_URL for asyncpg driver.

    - Converts postgres:// to postgresql://
    - Strips existing driver suffixes (e.g., +psycopg2)
    - Adds +asyncpg driver suffix
    - Preserves already-correct postgresql+asyncpg:// URLs
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.split("://", 1)[1]
    # Strip any existing driver suffix from the scheme only
    if url.startswith("postgresql+"):
        scheme, rest = url.split("://", 1)
        base_scheme = scheme.split("+", 1)[0]
        url = f"{base_scheme}://{rest}"
    if not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _get_url() -> str:
    """Get and normalize DATABASE_URL from environment."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return _normalize_url(url)


def get_engine() -> AsyncEngine:
    """Get or create the async engine (lazy singleton)."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _get_url(),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _engine


def get_session_local() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory (lazy singleton)."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session without auto-commit (routes control transactions)."""
    async with get_session_local()() as session:
        yield session


def __getattr__(name: str):  # noqa: F811
    """Lazy attribute access for module-level engine and SessionLocal."""
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_local()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
