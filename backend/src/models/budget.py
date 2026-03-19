"""Budget entry and settings models."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BudgetEntry(Base, TimestampMixin):
    __tablename__ = "budget_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )


class BudgetSettings(Base, TimestampMixin):
    __tablename__ = "budget_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, unique=True
    )
    weekly_limit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="80.00"
    )
    total_savings: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0.00"
    )
