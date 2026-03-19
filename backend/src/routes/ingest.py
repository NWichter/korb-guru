"""Ingest endpoint — accepts scraped product records, upserts to Postgres + Qdrant.

Also handles Apify webhook notifications to auto-fetch and ingest scraper results.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field, field_validator
from qdrant_client import models
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..auth import require_ingest_auth
from ..db import get_session_local
from ..models.product import Product
from ..qdrant.client import get_qdrant_client
from ..services.embedding_service import embed_texts

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])

SPARSE_DIM = 2**20
QDRANT_COLLECTION = "products"


def _sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Build sparse BM25-style vector from tokenised text."""
    tokens = text.lower().split()
    seen: dict[int, int] = {}
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % SPARSE_DIM
        seen[h] = seen.get(h, 0) + 1
    return list(seen.keys()), [float(v) for v in seen.values()]


def _deterministic_uuid(retailer: str, name: str) -> uuid.UUID:
    """Generate a deterministic UUID from retailer:name using MD5."""
    hex_digest = hashlib.md5(f"{retailer}:{name}".encode()).hexdigest()
    return uuid.UUID(hex_digest)


class ProductRecord(BaseModel):
    """Validated product record from a scraper."""

    retailer: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=2000)
    price: Decimal | None = None
    original_price: Decimal | None = Field(None, alias="originalPrice")
    discount_pct: float | None = Field(None, alias="discountPct")
    category: str | None = Field(None, max_length=200)
    image_url: str | None = Field(None, alias="imageUrl")
    valid_from: date | None = Field(None, alias="validFrom")
    valid_to: date | None = Field(None, alias="validTo")
    ean: str | None = Field(None, max_length=50)
    allergens: str | None = Field(None, max_length=500)
    nutriscore: str | None = Field(None, max_length=5)
    nutritional_info: str | None = Field(None, alias="nutritionalInfo", max_length=2000)
    region: str = "zurich"

    model_config = {"populate_by_name": True}

    @field_validator("retailer", "name")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be blank after stripping whitespace")
        return stripped


class IngestRequest(BaseModel):
    source: str = "scraper"
    sink: str = "stdout"
    record_count: int | None = Field(None, alias="recordCount")
    records: list[ProductRecord] = Field(default_factory=list)
    region: str = "zurich"


class IngestResponse(BaseModel):
    status: str
    accepted: int
    source: str


async def _process_records(
    records: list[ProductRecord], source: str, default_region: str
) -> None:
    """Background task: upsert products to Postgres and Qdrant."""
    if not records:
        return

    # --- Build Qdrant points first (embedding can fail before any DB writes) ---
    names = [rec.name for rec in records]
    embeddings = await asyncio.to_thread(embed_texts, names)

    points = []
    for rec, dense_vector in zip(records, embeddings):
        product_id = _deterministic_uuid(rec.retailer, rec.name)
        sparse_indices, sparse_values = _sparse_vector(rec.name)
        region = rec.region or default_region

        payload: dict[str, Any] = {
            "retailer": rec.retailer,
            "name": rec.name,
            "region": region,
        }
        if rec.category is not None:
            payload["category"] = rec.category
        if rec.price is not None:
            payload["price"] = float(rec.price)
        if rec.discount_pct is not None:
            payload["discount_pct"] = rec.discount_pct
        if rec.valid_to is not None:
            payload["valid_to"] = rec.valid_to.isoformat()
        if rec.allergens is not None:
            payload["allergens"] = rec.allergens
        if rec.nutriscore is not None:
            payload["nutriscore"] = rec.nutriscore

        points.append(
            models.PointStruct(
                id=product_id.hex,
                vector={
                    "dense": dense_vector,
                    "sparse": models.SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                },
                payload=payload,
            )
        )

    # --- Postgres upsert first, then Qdrant (eventual consistency) ---
    session_factory = get_session_local()
    try:
        async with session_factory() as session:
            async with session.begin():
                for rec in records:
                    pid = _deterministic_uuid(rec.retailer, rec.name)
                    stmt = pg_insert(Product).values(
                        id=pid,
                        retailer=rec.retailer,
                        name=rec.name,
                        description=rec.description,
                        price=rec.price,
                        original_price=rec.original_price,
                        discount_pct=rec.discount_pct,
                        category=rec.category,
                        image_url=rec.image_url,
                        valid_from=rec.valid_from,
                        valid_to=rec.valid_to,
                        ean=rec.ean,
                        allergens=rec.allergens,
                        nutriscore=rec.nutriscore,
                        nutritional_info=rec.nutritional_info,
                        source=source,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "description": stmt.excluded.description,
                            "price": stmt.excluded.price,
                            "original_price": (stmt.excluded.original_price),
                            "discount_pct": (stmt.excluded.discount_pct),
                            "category": stmt.excluded.category,
                            "image_url": stmt.excluded.image_url,
                            "valid_from": stmt.excluded.valid_from,
                            "valid_to": stmt.excluded.valid_to,
                            "ean": stmt.excluded.ean,
                            "allergens": stmt.excluded.allergens,
                            "nutriscore": stmt.excluded.nutriscore,
                            "nutritional_info": stmt.excluded.nutritional_info,
                            "source": stmt.excluded.source,
                        },
                    )
                    await session.execute(stmt)
        logger.info(
            "Postgres upsert complete for %d records",
            len(records),
        )
    except Exception:
        logger.exception("Ingest failed (Postgres)")
        raise

    # Qdrant upsert runs after Postgres commit. If it fails,
    # Postgres keeps its data (eventual consistency is fine).
    try:
        client = get_qdrant_client()
        await asyncio.to_thread(
            client.upsert,
            collection_name=QDRANT_COLLECTION,
            points=points,
        )
        logger.info("Qdrant upsert complete for %d points", len(points))
    except Exception:
        logger.exception(
            "Qdrant upsert failed for %d points; Postgres data was committed",
            len(points),
        )


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_records(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    _auth: Annotated[None, Depends(require_ingest_auth)] = None,
) -> IngestResponse:
    if payload.records:
        background_tasks.add_task(
            _process_records,
            payload.records,
            payload.source,
            payload.region,
        )

    return IngestResponse(
        status="accepted",
        accepted=len(payload.records),
        source=payload.source,
    )


# ---------------------------------------------------------------------------
# Apify Webhook Handler
# ---------------------------------------------------------------------------


class ApifyResource(BaseModel):
    """Nested resource object from Apify webhook payload."""

    default_dataset_id: str | None = Field(None, alias="defaultDatasetId")


class WebhookPayload(BaseModel):
    """Payload sent by the swiss-grocery-scraper actor after a run."""

    event: str = "scrape_completed"
    total_items: int = Field(0, alias="totalItems")
    region: str = "zurich"
    retailers: list[str] = Field(default_factory=list)
    duration_s: float = Field(0, alias="durationS")
    resource: ApifyResource | None = None

    model_config = {"populate_by_name": True}


class WebhookResponse(BaseModel):
    status: str
    message: str


async def _fetch_and_ingest_from_apify(
    region: str, retailers: list[str], dataset_id: str | None = None
) -> None:
    """Background task: fetch Apify dataset and ingest via _process_records."""
    apify_token = os.getenv("APIFY_TOKEN")
    if not apify_token:
        logger.error("APIFY_TOKEN not set — cannot fetch from Apify")
        return

    try:
        from apify_client import ApifyClient

        client = ApifyClient(apify_token)

        if not dataset_id:
            # Fallback: fetch the latest run's dataset (legacy behavior)
            actor_id = "korb-guru/swiss-grocery-scraper"
            runs = await asyncio.to_thread(
                client.actor(actor_id).runs().list, limit=1, desc=True
            )
            if not runs.items:
                logger.warning("No runs found for actor %s", actor_id)
                return

            latest_run = runs.items[0]
            dataset_id = latest_run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning("No dataset ID in latest run")
                return

        items = (await asyncio.to_thread(client.dataset(dataset_id).list_items)).items
        logger.info("Fetched %d items from Apify dataset %s", len(items), dataset_id)

        if not items:
            return

        # Convert raw Apify items to ProductRecord format
        records = []
        for item in items:
            name = item.get("name", "").strip()
            retailer = item.get("retailer", "").strip()
            if not name or not retailer:
                continue

            price = item.get("price")
            if isinstance(price, str):
                try:
                    price = Decimal(price.replace("CHF", "").replace(",", ".").strip())
                except Exception:
                    price = None

            records.append(
                ProductRecord(
                    retailer=retailer,
                    name=name,
                    price=price,
                    discount_pct=item.get("discount_pct"),
                    category=item.get("category"),
                    image_url=item.get("image_url"),
                    region=item.get("region", region),
                )
            )

        logger.info("Processing %d records from webhook", len(records))
        await _process_records(records, "apify-webhook", region)

    except Exception:
        logger.exception("Failed to fetch and ingest from Apify")


@router.post(
    "/webhook/apify",
    response_model=WebhookResponse,
    status_code=202,
)
async def apify_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    _auth: Annotated[None, Depends(require_ingest_auth)] = None,
) -> WebhookResponse:
    """Handle Apify actor completion webhook.

    When the swiss-grocery-scraper finishes, it POSTs here.
    We then fetch the latest dataset from Apify and ingest it.
    """
    logger.info(
        "Apify webhook received: event=%s, items=%d, region=%s, retailers=%s",
        payload.event,
        payload.total_items,
        payload.region,
        payload.retailers,
    )

    if payload.total_items > 0:
        dataset_id = payload.resource.default_dataset_id if payload.resource else None
        background_tasks.add_task(
            _fetch_and_ingest_from_apify,
            payload.region,
            payload.retailers,
            dataset_id,
        )

    return WebhookResponse(
        status="accepted",
        message=f"Will ingest {payload.total_items} items from Apify",
    )
