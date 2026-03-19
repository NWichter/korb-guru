"""Product schemas."""

from datetime import date

from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    id: str
    retailer: str
    name: str
    description: str | None
    price: float | None
    original_price: float | None
    discount_pct: float | None
    category: str | None
    image_url: str | None
    valid_from: date | None
    valid_to: date | None
    score: float | None = None


class ProductSearchRequest(BaseModel):
    query: str
    retailers: list[str] | None = None
    max_price: float | None = None
    category: str | None = None
    limit: int = 10


class ProductFeedbackRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=200)
    helpful: bool
