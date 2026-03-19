"""
Factory Boy test fixtures for creating test data.

Uses async_factory_boy for async SQLAlchemy session support.
"""

import uuid

import factory
from async_factory_boy.factory.sqlalchemy import AsyncSQLAlchemyFactory

from src.models.user import User


class UserFactory(AsyncSQLAlchemyFactory):
    """Factory for creating User instances in tests."""

    class Meta:
        model = User
        # Session is injected by the db_session fixture at test time
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    clerk_id = factory.Sequence(lambda n: f"clerk_{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
