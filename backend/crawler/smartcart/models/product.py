from datetime import date

from pydantic import BaseModel, field_validator

from crawler.smartcart.config import PRICE_MIN, PRICE_MAX


class ScrapedProduct(BaseModel):
    retailer: str
    name: str
    description: str | None = None
    price: float | None = None
    original_price: float | None = None
    discount_pct: float | None = None
    category: str | None = None
    image_url: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("price", "original_price", mode="before")
    @classmethod
    def validate_price(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not PRICE_MIN <= v <= PRICE_MAX:
            return None
        return round(v, 2)


class ScrapedProspekt(BaseModel):
    chain: str
    type: str
    region: str = "ZH"
    kw: str
    year: int
    valid_from: str
    valid_to: str
    url: str | None = None
    title: str | None = None
    description: str | None = None
    products: list[ScrapedProduct] = []
