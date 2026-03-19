"""Grocery list and item models."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class GroceryList(Base, TimestampMixin):
    __tablename__ = "grocery_lists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("households.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Shopping List"
    )
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.0
    )


class GroceryItem(Base):
    __tablename__ = "grocery_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    grocery_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("grocery_lists.id"), nullable=False, index=True
    )
    ingredient_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Other")
    is_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
