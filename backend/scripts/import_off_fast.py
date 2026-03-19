"""Fast OFF import — Phase 1: bulk fetch, Phase 2: bulk DB, Phase 3: bulk embed."""

import asyncio
import hashlib
import logging
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("off-fast")

import httpx  # noqa: E402
from qdrant_client import models  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.qdrant.client import get_qdrant_client  # noqa: E402
from src.services.embedding_service import embed_texts  # noqa: E402

PRICE_RANGES = {
    "dairy": (1.2, 8.5),
    "fruits": (1.5, 5.9),
    "vegetables": (0.9, 4.5),
    "meat": (4.5, 25),
    "bakery": (1.2, 6.5),
    "beverages": (0.8, 4.5),
    "snacks": (1.5, 6.9),
    "frozen": (2.5, 12),
    "sweets": (1.8, 6.9),
    "breakfast": (2.5, 8.9),
    "alcohol": (2.5, 25),
    "hygiene": (2, 9.9),
}
CAT_KW = {
    "dairy": ["milch", "käse", "joghurt", "butter", "rahm", "fromage"],
    "fruits": ["frucht", "früchte", "obst", "apfel", "banane", "fruit"],
    "vegetables": ["gemüse", "salat", "tomate", "karotte", "kartoffel"],
    "meat": ["fleisch", "poulet", "rind", "schwein", "wurst", "viande"],
    "bakery": ["brot", "gipfeli", "zopf", "toast", "pain"],
    "beverages": ["wasser", "saft", "tee", "kaffee", "bier", "wein"],
    "snacks": ["chips", "nüsse", "riegel", "cracker", "snack"],
    "frozen": ["tiefkühl", "eis", "pizza", "frozen", "glacé"],
    "sweets": ["schokolade", "bonbon", "zucker", "chocolat"],
    "breakfast": ["müesli", "cornflakes", "haferflocken", "honig"],
    "alcohol": ["bier", "wein", "whisky", "vodka", "gin", "rum"],
    "hygiene": ["seife", "shampoo", "zahnpasta", "duschgel"],
}
ALLERGEN_MAP = {
    "en:milk": "milk",
    "en:gluten": "gluten",
    "en:nuts": "nuts",
    "en:eggs": "eggs",
    "en:soybeans": "soy",
}
VALID_NUTRI = {"a", "b", "c", "d", "e"}
SPARSE_DIM = 2**20


def _cat(tags):
    t = " ".join(tags).lower()
    for c, kws in CAT_KW.items():
        for k in kws:
            if k in t:
                return c
    return None


def _price(c, name):
    lo, hi = PRICE_RANGES.get(c or "", (1.5, 8))
    if "bio" in name.lower():
        lo, hi = lo * 1.3, hi * 1.3
    s = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return round(round(random.Random(s).uniform(lo, hi) * 20) / 20, 2)


def _map(raw):
    name = raw.get("product_name_de")
    code = raw.get("code")
    if not name or not code or len(name.strip()) < 2:
        return None
    c = _cat(raw.get("categories_tags_de") or [])
    atags = raw.get("allergens_tags") or []
    allergens = ",".join(ALLERGEN_MAP[a] for a in atags if a in ALLERGEN_MAP) or None
    ns = raw.get("nutriscore_grade")
    return {
        "id": hashlib.md5(f"off:{code}".encode()).hexdigest(),
        "ean": code[:20],
        "name": name.strip()[:500],
        "retailer": "other",
        "price": _price(c, name.strip()),
        "category": c,
        "image_url": raw.get("image_front_small_url"),
        "allergens": allergens,
        "nutriscore": ns if ns in VALID_NUTRI else None,
    }


async def main():
    # ── Phase 1: Fetch all products (parallel pages) ──
    log.info("Phase 1: Fetching from Open Food Facts...")
    products = []
    page = 1
    consecutive_empty = 0

    async with httpx.AsyncClient(timeout=60.0) as http:
        while True:
            try:
                r = await http.get(
                    "https://world.openfoodfacts.org/api/v2/search",
                    params={
                        "countries_tags_en": "Switzerland",
                        "page_size": 100,
                        "page": page,
                        "fields": "code,product_name_de,brands,"
                        "categories_tags_de,image_front_small_url,"
                        "nutriscore_grade,allergens_tags",
                        "sort_by": "unique_scans_n",
                    },
                )
                data = r.json()
                raw = data.get("products", [])
            except Exception:
                log.warning("Page %d failed, skip", page)
                page += 1
                consecutive_empty += 1
                if consecutive_empty > 10:
                    break
                await asyncio.sleep(2)
                continue

            if not raw:
                consecutive_empty += 1
                if consecutive_empty > 3:
                    break
                page += 1
                continue

            consecutive_empty = 0
            for r in raw:
                m = _map(r)
                if m:
                    products.append(m)

            if page % 50 == 0:
                log.info("Fetch page %d: %d products so far", page, len(products))

            page += 1
            await asyncio.sleep(0.5)  # 2 req/sec (OFF limit is ~1-2/sec)

    log.info("Phase 1 done: %d products from %d pages", len(products), page)

    # ── Phase 2: Bulk DB insert ──
    log.info("Phase 2: Bulk inserting into PostgreSQL...")
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession)

    batch_size = 500
    total_pg = 0
    async with async_session() as session:
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            for p in batch:
                await session.execute(
                    text(
                        "INSERT INTO products "
                        "(id,retailer,name,price,category,image_url,"
                        "source,ean,allergens,nutriscore) "
                        "VALUES (:id,:retailer,:name,:price,:category,"
                        ":image_url,'openfoodfacts',:ean,:allergens,"
                        ":nutriscore) "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "name=EXCLUDED.name,price=EXCLUDED.price,"
                        "allergens=EXCLUDED.allergens,"
                        "nutriscore=EXCLUDED.nutriscore,"
                        "image_url=EXCLUDED.image_url"
                    ),
                    p,
                )
            await session.commit()
            total_pg += len(batch)
            if total_pg % 5000 == 0:
                log.info("PG: %d / %d", total_pg, len(products))

    log.info("Phase 2 done: %d rows upserted", total_pg)

    # ── Phase 3: Bulk embed + Qdrant upsert ──
    log.info("Phase 3: Embedding + Qdrant upsert...")
    client = get_qdrant_client()
    embed_batch = 500
    total_qd = 0

    for i in range(0, len(products), embed_batch):
        batch = products[i : i + embed_batch]
        names = [p["name"] for p in batch]
        try:
            vecs = embed_texts(names)
        except Exception:
            log.warning("Embed batch %d failed, skip", i)
            continue

        points = []
        for p, v in zip(batch, vecs):
            tokens = p["name"].lower().split()
            seen = {}
            for t in tokens:
                h = int(hashlib.md5(t.encode()).hexdigest(), 16) % SPARSE_DIM
                seen[h] = seen.get(h, 0) + 1
            payload = {
                "retailer": p["retailer"],
                "name": p["name"],
                "category": p["category"],
                "source": "openfoodfacts",
            }
            if p["allergens"]:
                payload["allergens"] = p["allergens"]
            if p["nutriscore"]:
                payload["nutriscore"] = p["nutriscore"]
            if p["price"]:
                payload["price"] = p["price"]
            points.append(
                models.PointStruct(
                    id=p["id"],
                    vector={
                        "dense": v,
                        "sparse": models.SparseVector(
                            indices=list(seen.keys()),
                            values=[float(x) for x in seen.values()],
                        ),
                    },
                    payload=payload,
                )
            )

        try:
            client.upsert(collection_name="products", points=points)
            total_qd += len(points)
        except Exception:
            log.warning("Qdrant batch %d failed, skip", i)

        if total_qd % 5000 == 0 and total_qd > 0:
            log.info("Qdrant: %d / %d", total_qd, len(products))

    log.info("Phase 3 done: %d points upserted", total_qd)
    log.info("=== COMPLETE: PG=%d Qdrant=%d ===", total_pg, total_qd)


if __name__ == "__main__":
    asyncio.run(main())
