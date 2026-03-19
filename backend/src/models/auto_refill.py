"""Auto-refill rule model."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AutoRefillRule(Base, TimestampMixin):
    __tablename__ = "auto_refill_rules"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "ingredient_name",
            name="uq_auto_refill_household_ingredient",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    ingredient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    threshold_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
