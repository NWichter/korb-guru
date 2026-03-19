"""Notification model — per-user alerts and updates."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="bell")
    color: Mapped[str] = mapped_column(
        String(50), nullable=False, default="bg-emerald-500"
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
