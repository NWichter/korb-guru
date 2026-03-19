"""Protected routes for current user: profile, health streak, deletion."""

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..schemas.auth import ProfileUpdate, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if body.username is not None:
        user.username = body.username
    if "avatar_url" in body.model_fields_set:
        user.avatar_url = body.avatar_url
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/health-streak")
async def get_health_streak(user: User = Depends(get_current_user)):
    return {"health_streak_days": user.health_streak_days}


@router.post("/health-streak/increment")
async def increment_health_streak(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(health_streak_days=User.health_streak_days + 1)
    )
    await session.commit()
    await session.refresh(user)
    return {"health_streak_days": user.health_streak_days}


@router.post("/health-streak/reset")
async def reset_health_streak(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(User).where(User.id == user.id).values(health_streak_days=0)
    )
    await session.commit()
    await session.refresh(user)
    return {"health_streak_days": user.health_streak_days}


@router.delete("/me")
async def delete_me(user: User = Depends(get_current_user)):
    """Account deletion stub (App Store compliance).

    Production: call Clerk Backend API.
    """
    return {"ok": True}
