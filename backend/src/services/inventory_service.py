"""Fake inventory generator — assigns products to stores with price variation."""

from __future__ import annotations

import logging
import random
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.product import Product
from ..models.store import Store
from ..models.store_product import StoreProduct

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def generate_store_inventory(
    session: AsyncSession, seed: int = 42
) -> dict[str, int]:
    """For each store, assign 70-90% of its retailer's products randomly.

    Local prices are varied +-5% from the product base price.
    Returns a summary dict with counts.
    """
    rng = random.Random(seed)

    # Clear existing store_products
    await session.execute(delete(StoreProduct))

    # Load all stores and products
    stores = (await session.execute(select(Store))).scalars().all()
    products = (await session.execute(select(Product))).scalars().all()

    # Group products by retailer
    products_by_retailer: dict[str, list[Product]] = {}
    for product in products:
        products_by_retailer.setdefault(product.retailer, []).append(product)

    total_assigned = 0
    stores_processed = 0

    for store in stores:
        retailer_products = products_by_retailer.get(store.brand, [])
        if not retailer_products:
            continue

        # Pick 70-90% of products for this store
        pick_pct = rng.uniform(0.70, 0.90)
        count = max(1, int(len(retailer_products) * pick_pct))
        selected = rng.sample(retailer_products, min(count, len(retailer_products)))

        for product in selected:
            # Vary price +-5%
            local_price: Decimal | None = None
            if product.price is not None:
                factor = rng.uniform(0.95, 1.05)
                local_price = (product.price * Decimal(str(factor))).quantize(
                    Decimal("0.01")
                )

            session.add(
                StoreProduct(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    product_id=product.id,
                    local_price=local_price,
                    in_stock=rng.random() > 0.05,  # 95% in stock
                )
            )
            total_assigned += 1

        stores_processed += 1

    await session.flush()
    logger.info(
        "Generated inventory: %d assignments across %d stores",
        total_assigned,
        stores_processed,
    )

    return {"stores_processed": stores_processed, "products_assigned": total_assigned}
