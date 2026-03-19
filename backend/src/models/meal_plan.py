"""MealPlan model — maps recipes to dates for weekly meal planning."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class MealPlan(Base, TimestampMixin):
    __tablename__ = "meal_plans"
    __table_args__ = (
        CheckConstraint(
            "meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name="ck_meal_plans_meal_slot",
        ),
        UniqueConstraint(
            "household_id",
            "planned_date",
            "meal_slot",
            name="uq_meal_plans_household_date_slot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, index=True
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id"), nullable=False
    )
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(20), nullable=False, default="dinner")
