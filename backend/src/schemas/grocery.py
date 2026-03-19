"""Grocery schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroceryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_name: str
    quantity: str | None
    category: str
    is_checked: bool


class GroceryListResponse(BaseModel):
    id: uuid.UUID
    name: str
    estimated_total: Decimal
    items: list[GroceryItemResponse] = []


class GroceryItemUpdate(BaseModel):
    is_checked: bool | None = None


class BulkCheckItem(BaseModel):
    item_id: uuid.UUID
    is_checked: bool


class BulkCheckRequest(BaseModel):
    updates: list[BulkCheckItem] = Field(min_length=1, max_length=100)


class GroceryItemCreate(BaseModel):
    ingredient_name: str = Field(min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    category: str = Field(default="Other", max_length=100)

    @field_validator("ingredient_name")
    @classmethod
    def strip_and_reject_blank_ingredient(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("ingredient_name must not be blank")
        return stripped


class BulkItemCreateRequest(BaseModel):
    items: list[GroceryItemCreate] = Field(min_length=1, max_length=100)


class BulkUpdateResponse(BaseModel):
    updated_count: int


class GroceryListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_and_reject_blank_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("List name must not be blank")
        return stripped
