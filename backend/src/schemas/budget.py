"""Budget schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetSettingsUpdate(BaseModel):
    weekly_limit: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )


class BudgetSettingsResponse(BaseModel):
    weekly_limit: Decimal
    total_savings: Decimal

    model_config = {"from_attributes": True}


class BudgetEntryCreate(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    description: str | None = Field(default=None, max_length=500)


class BudgetEntryResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    description: str | None
    recorded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class WeeklySummaryResponse(BaseModel):
    weekly_limit: Decimal
    spent_this_week: Decimal
    remaining: Decimal
    total_savings: Decimal
