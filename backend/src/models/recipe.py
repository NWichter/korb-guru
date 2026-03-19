"""Recipe, RecipeIngredient, and SwipeAction models."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Recipe(Base, TimestampMixin):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint(
            "type IN ('protein', 'veggie', 'carb')",
            name="ck_recipe_type_values",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # protein/veggie/carb
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True, index=True
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)


class SwipeAction(Base, TimestampMixin):
    """Tracks accept/reject swipe per user+recipe.

    The unique constraint on (user_id, recipe_id) means ON CONFLICT updates the
    existing row. Queries that need recency ranking (e.g. context pairs) should
    ORDER BY updated_at, not created_at, to reflect the latest swipe decision.
    """

    __tablename__ = "swipe_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_swipe_actions_user_recipe"),
        CheckConstraint(
            "action IN ('accept', 'reject')",
            name="ck_swipe_action_values",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # accept/reject
