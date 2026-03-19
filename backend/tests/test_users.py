"""
Tests for User model using async factory pattern.
"""

import uuid

import pytest
from sqlalchemy import select

from src.models.user import User
from tests.factories import UserFactory


@pytest.mark.asyncio
async def test_create_user_with_factory(db_session):
    """Test creating a User via UserFactory."""
    UserFactory._meta.sqlalchemy_session = db_session

    user = await UserFactory.create()

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email is not None
    assert user.clerk_id is not None
    assert user.username is not None


@pytest.mark.asyncio
async def test_user_email_is_unique(db_session):
    """Test that factory generates unique emails."""
    UserFactory._meta.sqlalchemy_session = db_session

    user1 = await UserFactory.create()
    user2 = await UserFactory.create()

    assert user1.email != user2.email
    assert user1.clerk_id != user2.clerk_id


@pytest.mark.asyncio
async def test_database_isolation(db_session):
    """Test that database is clean between tests (isolation)."""
    result = await db_session.execute(select(User))
    users = result.scalars().all()

    # Should be empty at start of test (isolation works)
    assert len(users) == 0

    UserFactory._meta.sqlalchemy_session = db_session

    user = await UserFactory.create()

    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1
    assert users[0].email == user.email
    assert users[0].clerk_id == user.clerk_id
