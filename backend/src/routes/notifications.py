"""User notifications — list, mark read, delete."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import Pagination, get_current_user, get_pagination
from ..models.notification import Notification
from ..models.user import User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    text: str
    icon: str
    color: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationActionResponse(BaseModel):
    status: str


@router.get("", response_model=list[NotificationResponse])
async def get_notifications(
    user: User = Depends(get_current_user),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    return result.scalars().all()


@router.patch("/{notification_id}", response_model=NotificationActionResponse)
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    n = await session.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    session.add(n)
    await session.commit()
    return {"status": "read"}


@router.delete("/{notification_id}", response_model=NotificationActionResponse)
async def delete_notification(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    n = await session.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    await session.delete(n)
    await session.commit()
    return {"status": "deleted"}
