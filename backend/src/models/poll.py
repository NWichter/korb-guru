"""Poll models — meal voting within households."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class MealPoll(Base, TimestampMixin):
    __tablename__ = "meal_polls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, index=True
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id"), nullable=False
    )
    proposed_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PollVote(Base, TimestampMixin):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "user_id", name="uq_poll_votes_poll_user"),
        CheckConstraint("vote IN ('yes', 'no')", name="ck_poll_votes_vote_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    poll_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("meal_polls.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    # Constrained to 'yes'/'no' via CheckConstraint
    vote: Mapped[str] = mapped_column(String(10), nullable=False)
