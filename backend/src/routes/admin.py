"""Admin endpoints — no auth required (dev only)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from qdrant_client import models
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.product import Product
from ..models.recipe import Recipe, RecipeIngredient
from ..models.store_product import StoreProduct
from ..qdrant.client import get_qdrant_client
from ..services.demo_data import generate_demo_products
from ..services.embedding_service import embed_texts
from ..services.inventory_service import generate_store_inventory
from ..services.openfoodfacts_service import fetch_swiss_products
from ..services.qdrant_cleanup import run_cleanup
from ..services.recipe_data import DEMO_RECIPES

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger(__name__)

SPARSE_DIM = 2**20


def _sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Build sparse BM25-style vector from tokenised text."""
    tokens = text.lower().split()
    seen: dict[int, int] = {}
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % SPARSE_DIM
        seen[h] = seen.get(h, 0) + 1
    return list(seen.keys()), [float(v) for v in seen.values()]


@router.post("/cleanup-qdrant")
def cleanup_qdrant():
    """Run Qdrant product cleanup: delete junk, re-embed cleaned names.

    Returns a report with deleted_count, cleaned_count, remaining_count.
    """
    report = run_cleanup()
    return report


class SeedResponse(BaseModel):
    status: str
    products_inserted: int
    products_embedded: int
    recipes_inserted: int
    recipes_embedded: int
    inventory: dict[str, int]


@router.post("/seed-demo", response_model=SeedResponse)
async def seed_demo(
    session: AsyncSession = Depends(get_db),
) -> SeedResponse:
    """Seed demo data: products, Qdrant vectors, inventory, and recipes.

    No auth required — intended for dev/staging use only.
    """
    # ── 1. Clear existing demo data (order matters for FKs) ─────
    await session.execute(delete(StoreProduct))
    demo_recipe_ids = select(Recipe.id).where(Recipe.created_by.is_(None))
    await session.execute(
        delete(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(demo_recipe_ids))
    )
    await session.execute(delete(Recipe).where(Recipe.created_by.is_(None)))
    await session.execute(delete(Product).where(Product.source == "demo"))
    await session.flush()

    # ── 2. Insert demo products into Postgres ───────────────────
    demo_products = generate_demo_products()
    for prod in demo_products:
        stmt = pg_insert(Product).values(
            id=prod["id"],
            retailer=prod["retailer"],
            name=prod["name"],
            price=prod["price"],
            category=prod["category"],
            discount_pct=prod["discount_pct"],
            image_url=prod["image_url"],
            source=prod["source"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "price": stmt.excluded.price,
                "category": stmt.excluded.category,
                "discount_pct": stmt.excluded.discount_pct,
                "source": stmt.excluded.source,
            },
        )
        await session.execute(stmt)
    await session.flush()
    logger.info("Inserted %d demo products into Postgres", len(demo_products))

    # ── 3. Embed and upsert products to Qdrant ─────────────────
    products_embedded = 0
    try:
        client = get_qdrant_client()
        batch_size = 50
        for i in range(0, len(demo_products), batch_size):
            batch = demo_products[i : i + batch_size]
            names = [p["name"] for p in batch]
            embeddings = await asyncio.to_thread(embed_texts, names)

            points = []
            for prod, dense_vector in zip(batch, embeddings):
                sparse_indices, sparse_values = _sparse_vector(prod["name"])
                payload: dict[str, Any] = {
                    "retailer": prod["retailer"],
                    "name": prod["name"],
                    "region": prod["region"],
                    "category": prod["category"],
                }
                if prod["price"] is not None:
                    payload["price"] = float(prod["price"])
                if prod["discount_pct"] is not None:
                    payload["discount_pct"] = prod["discount_pct"]

                points.append(
                    models.PointStruct(
                        id=prod["id"].hex,
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

            await asyncio.to_thread(
                client.upsert,
                collection_name="products",
                points=points,
            )
            products_embedded += len(points)

        logger.info("Embedded %d products to Qdrant", products_embedded)
    except Exception:
        logger.exception("Qdrant product upsert failed; Postgres data was committed")

    # ── 4. Generate fake store inventory ────────────────────────
    inventory = await generate_store_inventory(session)

    # ── 5. Create demo recipes ──────────────────────────────────
    recipes_inserted = 0
    recipes_embedded = 0

    recipe_embed_queue: list[tuple[Recipe, list[RecipeIngredient]]] = []
    for recipe_data in DEMO_RECIPES:
        recipe = Recipe(
            id=uuid.uuid4(),
            title=recipe_data["title"],
            description=recipe_data["description"],
            cost=Decimal(str(recipe_data["cost"])),
            time_minutes=recipe_data["time_minutes"],
            type=recipe_data["type"],
            household_id=None,
            created_by=None,
        )
        session.add(recipe)
        await session.flush()

        ingredients = []
        for ing in recipe_data["ingredients"]:
            ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                name=ing["name"],
                quantity=ing.get("quantity"),
                unit=ing.get("unit"),
            )
            session.add(ingredient)
            ingredients.append(ingredient)

        recipes_inserted += 1
        recipe_embed_queue.append((recipe, ingredients))

    await session.commit()

    # Best-effort Qdrant upsert for recipes (after Postgres commit)
    for recipe, ingredients in recipe_embed_queue:
        try:
            text = (
                f"{recipe.title} {recipe.description or ''} "
                f"{' '.join(i.name for i in ingredients)}"
            )
            vector = await asyncio.to_thread(embed_texts, [text])
            client = get_qdrant_client()
            await asyncio.to_thread(
                client.upsert,
                collection_name="recipes",
                points=[
                    models.PointStruct(
                        id=str(recipe.id),
                        vector=vector[0],
                        payload={
                            "recipe_id": str(recipe.id),
                            "type": recipe.type,
                            "cost": float(recipe.cost),
                            "time_minutes": recipe.time_minutes,
                            "household_id": None,
                        },
                    )
                ],
            )
            recipes_embedded += 1
        except Exception:
            logger.exception("Failed to embed recipe %s", recipe.title)
    logger.info(
        "Seed complete: %d products, %d recipes, inventory=%s",
        len(demo_products),
        recipes_inserted,
        inventory,
    )

    return SeedResponse(
        status="ok",
        products_inserted=len(demo_products),
        products_embedded=products_embedded,
        recipes_inserted=recipes_inserted,
        recipes_embedded=recipes_embedded,
        inventory=inventory,
    )


class OFFImportResponse(BaseModel):
    status: str
    products_fetched: int
    products_inserted: int
    products_embedded: int
    inventory: dict[str, int]


@router.post("/import-openfoodfacts", response_model=OFFImportResponse)
async def import_openfoodfacts(
    max_products: int = Query(default=200_000, ge=1),
    session: AsyncSession = Depends(get_db),
) -> OFFImportResponse:
    """Import Swiss products from Open Food Facts into Postgres + Qdrant.

    Incremental: can be re-run safely (upserts by deterministic UUID).
    No auth required — intended for dev/staging use only.
    """
    # ── 1. Fetch products from OFF ───────────────────────────────
    products = await fetch_swiss_products(max_products=max_products)
    if not products:
        return OFFImportResponse(
            status="ok",
            products_fetched=0,
            products_inserted=0,
            products_embedded=0,
            inventory={"stores_processed": 0, "products_assigned": 0},
        )

    logger.info("Fetched %d products from Open Food Facts", len(products))

    # ── 2. Upsert into PostgreSQL ────────────────────────────────
    products_inserted = 0
    for prod in products:
        stmt = pg_insert(Product).values(
            id=prod["id"],
            ean=prod["ean"],
            retailer=prod["retailer"],
            name=prod["name"],
            description=prod["description"],
            price=prod["price"],
            original_price=prod["original_price"],
            discount_pct=prod["discount_pct"],
            category=prod["category"],
            image_url=prod["image_url"],
            allergens=prod["allergens"],
            nutriscore=prod["nutriscore"],
            nutritional_info=prod["nutritional_info"],
            source=prod["source"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "ean": stmt.excluded.ean,
                "retailer": stmt.excluded.retailer,
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "category": stmt.excluded.category,
                "image_url": stmt.excluded.image_url,
                "allergens": stmt.excluded.allergens,
                "nutriscore": stmt.excluded.nutriscore,
                "nutritional_info": stmt.excluded.nutritional_info,
                "source": stmt.excluded.source,
            },
        )
        await session.execute(stmt)
        products_inserted += 1

        if products_inserted % 1000 == 0:
            logger.info(
                "PostgreSQL upsert progress: %d/%d", products_inserted, len(products)
            )

    await session.flush()
    logger.info("Upserted %d OFF products into PostgreSQL", products_inserted)

    # ── 3. Embed and upsert to Qdrant ────────────────────────────
    products_embedded = 0
    try:
        client = get_qdrant_client()
        batch_size = 100
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            names = [p["name"] for p in batch]
            embeddings = await asyncio.to_thread(embed_texts, names)

            points = []
            for prod, dense_vector in zip(batch, embeddings):
                sparse_indices, sparse_values = _sparse_vector(prod["name"])
                payload: dict[str, Any] = {
                    "retailer": prod["retailer"],
                    "name": prod["name"],
                    "category": prod["category"],
                    "source": "openfoodfacts",
                }
                if prod["allergens"]:
                    payload["allergens"] = prod["allergens"]
                if prod["nutriscore"]:
                    payload["nutriscore"] = prod["nutriscore"]
                if prod["price"] is not None:
                    payload["price"] = float(prod["price"])

                points.append(
                    models.PointStruct(
                        id=prod["id"].hex,
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

            await asyncio.to_thread(
                client.upsert,
                collection_name="products",
                points=points,
            )
            products_embedded += len(points)

            if products_embedded % 1000 < batch_size:
                logger.info(
                    "Qdrant upsert progress: %d/%d", products_embedded, len(products)
                )

        logger.info("Embedded %d OFF products to Qdrant", products_embedded)
    except Exception:
        logger.exception(
            "Qdrant upsert failed for OFF products; Postgres data preserved"
        )

    # ── 4. Generate store inventory for imported products ─────────
    inventory = await generate_store_inventory(session)

    await session.commit()
    logger.info(
        "OFF import complete: %d fetched, %d inserted, %d embedded, inventory=%s",
        len(products),
        products_inserted,
        products_embedded,
        inventory,
    )

    return OFFImportResponse(
        status="ok",
        products_fetched=len(products),
        products_inserted=products_inserted,
        products_embedded=products_embedded,
        inventory=inventory,
    )
