"""Import Swiss products from Open Food Facts into PostgreSQL + Qdrant."""

import asyncio
import hashlib
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from qdrant_client import models
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.qdrant.client import get_qdrant_client
    from src.services.embedding_service import embed_texts
    from src.services.openfoodfacts_service import fetch_swiss_products

    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession)

    # 1. Fetch products
    logger.info("Fetching Swiss products from Open Food Facts...")
    products = await fetch_swiss_products(max_products=200_000)
    logger.info("Fetched %d products", len(products))

    # 2. Insert into PostgreSQL
    async with async_session() as session:
        inserted = 0
        for i, prod in enumerate(products):
            pid = uuid.UUID(hashlib.md5(f"off:{prod['ean']}".encode()).hexdigest())
            await session.execute(
                text("""
                    INSERT INTO products (
                        id, retailer, name, price, category,
                        image_url, source, ean, allergens,
                        nutriscore, nutritional_info
                    ) VALUES (
                        :id, :retailer, :name, :price, :category,
                        :image_url, 'openfoodfacts', :ean, :allergens,
                        :nutriscore, :nutritional_info
                    ) ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        allergens = EXCLUDED.allergens,
                        nutriscore = EXCLUDED.nutriscore,
                        image_url = EXCLUDED.image_url,
                        nutritional_info = EXCLUDED.nutritional_info
                """),
                {
                    "id": str(pid),
                    "retailer": prod.get("retailer", "other"),
                    "name": prod["name"],
                    "price": prod.get("price"),
                    "category": prod.get("category"),
                    "image_url": prod.get("image_url"),
                    "ean": prod.get("ean"),
                    "allergens": prod.get("allergens"),
                    "nutriscore": prod.get("nutriscore"),
                    "nutritional_info": prod.get("nutritional_info"),
                },
            )
            inserted += 1
            if inserted % 5000 == 0:
                await session.commit()
                logger.info("PG: %d / %d inserted", inserted, len(products))

        await session.commit()
        logger.info("PG: %d total inserted", inserted)

    # 3. Embed and upsert to Qdrant
    client = get_qdrant_client()
    embedded = 0
    batch_size = 200
    sparse_dim = 2**20

    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        names = [p["name"] for p in batch]
        vectors = embed_texts(names)

        points = []
        for prod, vec in zip(batch, vectors):
            pid = hashlib.md5(f"off:{prod['ean']}".encode()).hexdigest()

            # Sparse vector
            tokens = prod["name"].lower().split()
            seen = {}
            for t in tokens:
                h = int(hashlib.md5(t.encode()).hexdigest(), 16) % sparse_dim
                seen[h] = seen.get(h, 0) + 1

            payload = {
                "retailer": prod.get("retailer", "other"),
                "name": prod["name"],
                "category": prod.get("category"),
                "source": "openfoodfacts",
            }
            if prod.get("allergens"):
                payload["allergens"] = prod["allergens"]
            if prod.get("nutriscore"):
                payload["nutriscore"] = prod["nutriscore"]
            if prod.get("price"):
                payload["price"] = float(prod["price"])

            points.append(
                models.PointStruct(
                    id=pid,
                    vector={
                        "dense": vec,
                        "sparse": models.SparseVector(
                            indices=list(seen.keys()),
                            values=[float(v) for v in seen.values()],
                        ),
                    },
                    payload=payload,
                )
            )

        client.upsert(collection_name="products", points=points)
        embedded += len(points)
        if embedded % 5000 == 0:
            logger.info("Qdrant: %d / %d embedded", embedded, len(products))

    logger.info("Qdrant: %d total embedded", embedded)
    logger.info("DONE! %d products imported", len(products))


if __name__ == "__main__":
    asyncio.run(main())
