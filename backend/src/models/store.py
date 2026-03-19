"""Store model — physical retail locations for route planning."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    google_place_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
