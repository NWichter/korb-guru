"""Budget settings and expense tracking."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import (
    Pagination,
    get_current_user,
    get_household_id,
    get_pagination,
)
from ..models.budget import BudgetEntry, BudgetSettings
from ..models.user import User
from ..schemas.budget import (
    BudgetEntryCreate,
    BudgetEntryResponse,
    BudgetSettingsResponse,
    BudgetSettingsUpdate,
    WeeklySummaryResponse,
)

router = APIRouter(prefix="/api/v1/budget", tags=["budget"])


async def _get_or_create_settings(
    household_id: uuid.UUID, session: AsyncSession
) -> BudgetSettings:
    result = await session.execute(
        select(BudgetSettings).where(BudgetSettings.household_id == household_id)
    )
    settings = result.scalars().first()
    if not settings:
        try:
            settings = BudgetSettings(household_id=household_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        except IntegrityError:
            await session.rollback()
            result = await session.execute(
                select(BudgetSettings).where(
                    BudgetSettings.household_id == household_id
                )
            )
            settings = result.scalars().first()
    if settings is None:
        raise RuntimeError("Failed to create or retrieve budget settings")
    return settings


@router.get("/settings", response_model=BudgetSettingsResponse)
async def get_settings(
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    return await _get_or_create_settings(household_id, session)


@router.patch("/settings", response_model=BudgetSettingsResponse)
async def update_settings(
    body: BudgetSettingsUpdate,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    s = await _get_or_create_settings(household_id, session)
    if body.weekly_limit is not None:
        s.weekly_limit = body.weekly_limit
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@router.post("/entries", response_model=BudgetEntryResponse, status_code=201)
async def add_entry(
    body: BudgetEntryCreate,
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    entry = BudgetEntry(
        household_id=household_id,
        amount=body.amount,
        description=body.description,
        recorded_by=user.id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("/entries", response_model=list[BudgetEntryResponse])
async def get_entries(
    household_id: uuid.UUID = Depends(get_household_id),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(BudgetEntry)
        .where(BudgetEntry.household_id == household_id)
        .order_by(BudgetEntry.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    return result.scalars().all()


@router.get("/weekly-summary", response_model=WeeklySummaryResponse)
async def weekly_summary(
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    s = await _get_or_create_settings(household_id, session)
    now = datetime.now(UTC)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    spent_result = await session.execute(
        select(func.coalesce(func.sum(BudgetEntry.amount), Decimal("0"))).where(
            BudgetEntry.household_id == household_id,
            BudgetEntry.created_at >= week_start,
        )
    )
    spent = Decimal(str(spent_result.scalar_one()))
    weekly_limit = Decimal(str(s.weekly_limit))
    remaining = weekly_limit - spent
    return WeeklySummaryResponse(
        weekly_limit=weekly_limit,
        spent_this_week=spent,
        remaining=remaining,
        total_savings=Decimal(str(s.total_savings)),
    )
