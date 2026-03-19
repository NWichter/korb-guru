"""Auth-related schemas — user profile responses and validation helpers."""

import uuid
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def validate_username(v: object) -> str:
    """Shared username validation: strip, check length, check characters."""
    if not isinstance(v, str):
        raise ValueError("Username must be a string")
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Username must be at least 2 characters after trimming")
    if not all(c.isalnum() or c in "-_ " for c in v):
        msg = "Username: letters, digits, hyphens, underscores, spaces only"
        raise ValueError(msg)
    return v


StrippedUsername = Annotated[str, BeforeValidator(validate_username)]


class ProfileUpdate(BaseModel):
    username: StrippedUsername | None = Field(default=None, min_length=2, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserResponse(BaseModel):
    id: uuid.UUID
    clerk_id: str
    email: str
    username: str
    avatar_url: str | None
    household_id: uuid.UUID | None
    health_streak_days: int

    model_config = {"from_attributes": True}
