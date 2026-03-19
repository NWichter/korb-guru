"""Message schemas."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator


def _strip_str(v: object) -> str:
    if isinstance(v, str):
        return v.strip()
    return v  # type: ignore[return-value]


StrippedStr = Annotated[str, BeforeValidator(_strip_str)]


class MessageCreate(BaseModel):
    text: StrippedStr = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def reject_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message text must not be blank")
        return v


class MessageResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str | None = None
    text: str
    message_type: str
    created_at: datetime
