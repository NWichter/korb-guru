"""
SQLAlchemy declarative base for async ORM models.

Uses SQLAlchemy 2.0 style with AsyncAttrs for async attribute loading
and a deterministic naming convention for stable Alembic autogenerate.
"""

from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for constraints and indexes.
# Stable names ensure Alembic autogenerate produces consistent migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Inherits from:
        - AsyncAttrs: Enables async attribute loading
          (e.g., await obj.awaitable_attrs.relation)
        - DeclarativeBase: SQLAlchemy 2.0 declarative base (replaces declarative_base())

    All models should inherit from this class to get:
        - Consistent naming conventions for constraints
        - Async attribute access support
        - Type-checked mappings
    """

    metadata: ClassVar[MetaData] = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.

    Both columns use timezone-aware datetimes (DateTime(timezone=True)).
    - created_at: Set once on insert via server_default=func.now()
    - updated_at: Updated on each update via onupdate=func.now()
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
