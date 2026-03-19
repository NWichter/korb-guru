"""Recipe schemas."""

import uuid
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class RecipeType(StrEnum):
    protein = "protein"
    veggie = "veggie"
    carb = "carb"


class SwipeActionEnum(StrEnum):
    accept = "accept"
    reject = "reject"


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=50)


class RecipeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    cost: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    time_minutes: int = Field(ge=1)
    type: RecipeType
    image_url: str | None = Field(default=None, max_length=500)
    ingredients: list[IngredientCreate] = Field(default=[], max_length=50)


class RecipeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    cost: Decimal
    time_minutes: int
    type: RecipeType
    image_url: str | None
    ingredients: list[IngredientCreate] = []


class SwipeRequest(BaseModel):
    action: SwipeActionEnum
