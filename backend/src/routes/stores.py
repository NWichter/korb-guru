"""Store management — ingestion from Google Maps, listing, and nearby search."""

from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_ingest_auth
from ..db import get_db
from ..dependencies import get_current_user
from ..models.product import Product
from ..models.store import Store
from ..models.store_product import StoreProduct
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])

# Mapping from Google Maps category names to our brand slugs
BRAND_MAP: dict[str, str] = {
    "migros": "migros",
    "coop": "coop",
    "aldi": "aldi",
    "aldi suisse": "aldi",
    "lidl": "lidl",
    "denner": "denner",
}


def _detect_brand(title: str, category: str | None) -> str | None:
    """Detect retailer brand from Google Maps place title or category."""
    for text in (title, category):
        if not text:
            continue
        text_lower = text.lower()
        for keyword, brand in BRAND_MAP.items():
            if keyword in text_lower:
                return brand
    return None


class GoogleMapsPlace(BaseModel):
    """A place record from the Google Maps Apify actor."""

    title: str
    address: str | None = None
    latitude: float = Field(alias="lat")
    longitude: float = Field(alias="lng")
    place_id: str = Field(alias="placeId")
    phone: str | None = None
    website: str | None = None
    total_score: float | None = Field(None, alias="totalScore")
    category_name: str | None = Field(None, alias="categoryName")
    opening_hours: list[dict] | None = Field(None, alias="openingHours")

    model_config = {"populate_by_name": True}


class StoreIngestRequest(BaseModel):
    """Request body for bulk store ingestion from Google Maps."""

    places: list[GoogleMapsPlace]
    region: str = "zurich"


class StoreIngestResponse(BaseModel):
    status: str
    upserted: int
    skipped: int


@router.post("/ingest", response_model=StoreIngestResponse, status_code=200)
async def ingest_stores(
    payload: StoreIngestRequest,
    session: AsyncSession = Depends(get_db),
    _auth: Annotated[None, Depends(require_ingest_auth)] = None,
) -> StoreIngestResponse:
    """Upsert stores from Google Maps actor data.

    Uses google_place_id for deduplication. Only accepts places
    matching known retailer brands.
    """
    upserted = 0
    skipped = 0

    for place in payload.places:
        brand = _detect_brand(place.title, place.category_name)
        if not brand:
            skipped += 1
            continue

        hours_json = (
            json.dumps(place.opening_hours, ensure_ascii=False)
            if place.opening_hours
            else None
        )

        update_fields = {
            "name": place.title,
            "brand": brand,
            "address": place.address,
            "latitude": place.latitude,
            "longitude": place.longitude,
            "google_place_id": place.place_id,
            "phone": place.phone,
            "website": place.website,
            "rating": place.total_score,
            "opening_hours": hours_json,
        }

        # Check for existing store by name+brand+address (covers pre-seeded
        # stores that have NULL google_place_id and thus can't match the
        # unique constraint).
        existing = (
            (
                await session.execute(
                    select(Store).where(
                        Store.name == place.title,
                        Store.brand == brand,
                        Store.address == place.address,
                    )
                )
            )
            .scalars()
            .first()
        )

        if existing:
            for key, value in update_fields.items():
                setattr(existing, key, value)
        else:
            stmt = pg_insert(Store).values(id=uuid.uuid4(), **update_fields)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_stores_google_place_id",
                set_={
                    "name": stmt.excluded.name,
                    "brand": stmt.excluded.brand,
                    "address": stmt.excluded.address,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "phone": stmt.excluded.phone,
                    "website": stmt.excluded.website,
                    "rating": stmt.excluded.rating,
                    "opening_hours": stmt.excluded.opening_hours,
                },
            )
            await session.execute(stmt)
        upserted += 1

    await session.commit()
    logger.info("Store ingest: %d upserted, %d skipped", upserted, skipped)

    return StoreIngestResponse(
        status="ok",
        upserted=upserted,
        skipped=skipped,
    )


@router.get("")
async def list_stores(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    brand: str | None = Query(None, description="Filter by brand"),
):
    """List all stores, optionally filtered by brand."""
    query = select(Store)
    if brand:
        query = query.where(Store.brand == brand.lower())
    query = query.order_by(Store.brand, Store.name)
    result = await session.execute(query)
    return result.scalars().all()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in kilometers between two lat/lng points."""
    earth_radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class NearbyStoreResponse(BaseModel):
    id: str
    name: str
    brand: str
    latitude: float
    longitude: float
    address: str | None = None
    distance_km: float


@router.get("/nearby", response_model=list[NearbyStoreResponse])
async def nearby_stores(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in km"),
    brand: str | None = Query(None, description="Filter by brand"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Find stores near a given location, sorted by distance.

    Uses Haversine distance calculation in Python (no PostGIS needed).
    """
    query = select(Store)
    if brand:
        query = query.where(Store.brand == brand.lower())
    result = await session.execute(query)
    stores = result.scalars().all()

    nearby: list[dict] = []
    for store in stores:
        dist = _haversine_km(lat, lng, store.latitude, store.longitude)
        if dist <= radius_km:
            nearby.append(
                {
                    "id": str(store.id),
                    "name": store.name,
                    "brand": store.brand,
                    "latitude": store.latitude,
                    "longitude": store.longitude,
                    "address": store.address,
                    "distance_km": round(dist, 2),
                }
            )

    nearby.sort(key=lambda s: s["distance_km"])
    return nearby


@router.get("/{store_id}/products")
async def store_products(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    in_stock: bool | None = Query(None, description="Filter by stock status"),
):
    """List products available at a specific store."""
    query = (
        select(StoreProduct, Product)
        .join(Product, StoreProduct.product_id == Product.id)
        .where(StoreProduct.store_id == store_id)
    )
    if in_stock is not None:
        query = query.where(StoreProduct.in_stock == in_stock)
    query = query.order_by(Product.category, Product.name)

    result = await session.execute(query)
    rows = result.all()
    return [
        {
            "store_product_id": str(sp.id),
            "product_id": str(p.id),
            "retailer": p.retailer,
            "name": p.name,
            "base_price": float(p.price) if p.price is not None else None,
            "local_price": float(sp.local_price)
            if sp.local_price is not None
            else None,
            "category": p.category,
            "discount_pct": p.discount_pct,
            "in_stock": sp.in_stock,
            "last_seen": sp.last_seen.isoformat() if sp.last_seen else None,
        }
        for sp, p in rows
    ]
