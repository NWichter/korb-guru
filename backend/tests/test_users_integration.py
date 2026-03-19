"""Integration tests for /api/v1/users/me."""

from collections.abc import AsyncIterator
from typing import cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.main import app
from tests.factories import UserFactory

JsonDict = dict[str, object]


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
class TestMeRoutes:
    async def test_get_me_auto_creates_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """First call to /me auto-creates the dev user."""
        _ = db_session

        response = await client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = cast(JsonDict, response.json())
        assert data["clerk_id"] == "dev_user"
        assert isinstance(data["id"], str)

    async def test_get_me_returns_existing_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Existing dev user is returned without creating a new one."""
        UserFactory._meta.sqlalchemy_session = db_session
        user = await UserFactory.create(
            clerk_id="dev_user",
            email="existing@example.com",
            username="existing_user",
        )

        response = await client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = cast(JsonDict, response.json())
        assert data["email"] == "existing@example.com"
        assert data["username"] == "existing_user"
        assert data["id"] == str(user.id)

    async def test_update_profile(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """PATCH /me updates username and avatar."""
        UserFactory._meta.sqlalchemy_session = db_session
        await UserFactory.create(
            clerk_id="dev_user",
            email="patch@example.com",
            username="old_name",
        )

        response = await client.patch(
            "/api/v1/users/me",
            json={
                "username": "new_name",
                "avatar_url": "https://img.example.com/a.png",
            },
        )

        assert response.status_code == 200
        data = cast(JsonDict, response.json())
        assert data["username"] == "new_name"
        assert data["avatar_url"] == "https://img.example.com/a.png"

    async def test_health_streak(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Health streak starts at 0 and can be incremented."""
        UserFactory._meta.sqlalchemy_session = db_session
        await UserFactory.create(clerk_id="dev_user", email="streak@example.com")

        response = await client.get("/api/v1/users/health-streak")
        assert response.status_code == 200
        assert response.json()["health_streak_days"] == 0

        response = await client.post("/api/v1/users/health-streak/increment")
        assert response.status_code == 200
        assert response.json()["health_streak_days"] == 1
