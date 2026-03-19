"""Shared FastAPI dependencies — pagination, household scoping, dev user."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models.household import Household
from .models.user import User

_logger = logging.getLogger(__name__)

_DEV_CLERK_ID = "dev_user"
_DEV_EMAIL = "dev@korb.guru"
_DEV_USERNAME = "dev-user"
_DEV_HOUSEHOLD_NAME = "Dev Household"


@dataclass
class Pagination:
    offset: int
    limit: int


def get_pagination(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
) -> Pagination:
    return Pagination(offset=offset, limit=limit)


async def _get_or_create_dev_user(session: AsyncSession) -> User:
    """Return the dev user, creating it (with a household) if it doesn't exist."""
    result = await session.execute(select(User).where(User.clerk_id == _DEV_CLERK_ID))
    user = result.scalars().first()
    if user is not None:
        return user

    try:
        user = User(
            clerk_id=_DEV_CLERK_ID,
            email=_DEV_EMAIL,
            username=_DEV_USERNAME,
        )
        session.add(user)
        await session.flush()

        household = Household(
            name=_DEV_HOUSEHOLD_NAME,
            invite_code="dev-invite-code",
            created_by=user.id,
        )
        session.add(household)
        await session.flush()

        user.household_id = household.id
        await session.commit()
        await session.refresh(user)
        _logger.info("Created dev user (clerk_id=%s) with Dev Household", _DEV_CLERK_ID)
        return user
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(User).where(User.clerk_id == _DEV_CLERK_ID)
        )
        user = result.scalars().first()
        if user is not None:
            return user
        raise


async def get_current_user(
    session: AsyncSession = Depends(get_db),
) -> User:
    """Always returns the dev user — auth is disabled."""
    return await _get_or_create_dev_user(session)


async def get_household_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    if user.household_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not in a household",
        )
    return user.household_id
