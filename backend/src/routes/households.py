"""Household CRUD — create, join, view, list members."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import get_current_user
from ..models.household import Household
from ..models.user import User
from ..schemas.household import (
    HouseholdCreate,
    HouseholdJoin,
    HouseholdMemberResponse,
    HouseholdResponse,
)

router = APIRouter(prefix="/api/v1/households", tags=["households"])


@router.post("", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
async def create_household(
    body: HouseholdCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    # Re-fetch user with FOR UPDATE to prevent concurrent create race condition
    user_result = await session.execute(
        select(User).where(User.id == user.id).with_for_update()
    )
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.household_id:
        raise HTTPException(status_code=400, detail="Already in a household")
    code = secrets.token_urlsafe(6)
    household = Household(name=body.name, invite_code=code, created_by=user.id)
    session.add(household)
    await session.flush()  # get household.id without committing
    user.household_id = household.id
    session.add(user)
    await session.commit()
    await session.refresh(household)
    return household


@router.post("/join", response_model=HouseholdResponse)
async def join_household(
    body: HouseholdJoin,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if user.household_id:
        raise HTTPException(status_code=400, detail="Already in a household")
    result = await session.execute(
        select(Household).where(Household.invite_code == body.invite_code)
    )
    household = result.scalars().first()
    if not household:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    # Re-fetch user with FOR UPDATE to prevent concurrent join race condition
    user_result = await session.execute(
        select(User).where(User.id == user.id).with_for_update()
    )
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.household_id:
        raise HTTPException(status_code=400, detail="Already in a household")
    user.household_id = household.id
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return household


@router.get("", response_model=HouseholdResponse)
async def get_household(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if not user.household_id:
        raise HTTPException(status_code=404, detail="Not in a household")
    return await session.get(Household, user.household_id)


@router.get("/members", response_model=list[HouseholdMemberResponse])
async def get_members(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if not user.household_id:
        raise HTTPException(status_code=404, detail="Not in a household")
    result = await session.execute(
        select(User).where(User.household_id == user.household_id)
    )
    return result.scalars().all()
