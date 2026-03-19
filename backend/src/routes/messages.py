"""Household chat messages."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import (
    Pagination,
    get_current_user,
    get_household_id,
    get_pagination,
)
from ..models.message import Message
from ..models.user import User
from ..schemas.message import MessageCreate, MessageResponse

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.get("", response_model=list[MessageResponse])
async def get_messages(
    household_id: uuid.UUID = Depends(get_household_id),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Message)
        .where(Message.household_id == household_id)
        .order_by(Message.created_at, Message.id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    messages = result.scalars().all()
    if not messages:
        return []
    user_ids = list({msg.user_id for msg in messages})
    users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    user_map = {u.id: u.username for u in users_result.scalars().all()}
    return [
        MessageResponse(
            id=msg.id,
            user_id=msg.user_id,
            username=user_map.get(msg.user_id),
            text=msg.text,
            message_type=msg.message_type,
            created_at=msg.created_at,
        )
        for msg in messages
    ]


@router.post("", response_model=MessageResponse)
async def send_message(
    body: MessageCreate,
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    msg = Message(household_id=household_id, user_id=user.id, text=body.text)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return MessageResponse(
        id=msg.id,
        user_id=msg.user_id,
        username=user.username,
        text=msg.text,
        message_type=msg.message_type,
        created_at=msg.created_at,
    )
