"""
User routes demonstrating get_db dependency pattern.
"""

from typing import Annotated, ClassVar

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import User

router = APIRouter(prefix="/users", tags=["users"])


def _is_duplicate_email_integrity_error(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower() if exc.orig is not None else str(exc).lower()
    return (
        "users_email_key" in message
        or "duplicate key value" in message
        or "unique constraint" in message
    ) and "email" in message


class UserCreate(BaseModel):
    email: EmailStr

    name: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


@router.get("", response_model=list[UserResponse])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]):
    """List all users."""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return users


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new user."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=user_in.email, name=user_in.name)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_email_integrity_error(exc):
            raise HTTPException(
                status_code=400, detail="Email already registered"
            ) from exc
        raise

    await db.refresh(user)
    return user
