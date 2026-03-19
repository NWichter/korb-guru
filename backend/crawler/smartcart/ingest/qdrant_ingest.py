"""Ingest scraped products into Qdrant."""
import hashlib
import logging

from qdrant_client import QdrantClient, models

from crawler.smartcart.models.product import ScrapedProduct

logger = logging.getLogger(__name__)

SPARSE_DIM = 2**20  # ~1M buckets, much fewer collisions


def _sparse_vector(text: str) -> models.SparseVector:
    """Deterministic sparse vector from token hashes (MD5-based)."""
    tokens = text.lower().split()
    seen: dict[int, int] = {}
    for t in tokens:
        h = int(hashlib.md5(t.encode()).hexdigest(), 16) % SPARSE_DIM
        seen[h] = seen.get(h, 0) + 1
    return models.SparseVector(
        indices=list(seen.keys()),
        values=[float(v) for v in seen.values()],
    )


def get_qdrant_client_from_env() -> QdrantClient:
    import os
    mode = os.getenv("QDRANT_MODE", "docker")
    if mode == "cloud":
        return QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
    elif mode == "docker":
        return QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", "6333")))
    elif mode == "memory":
        return QdrantClient(":memory:")
    else:
        return QdrantClient(path="./qdrant_data")


def embed_products(products: list[ScrapedProduct]) -> list[list[float]]:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    texts = [f"{p.name} {p.description or ''} {p.category or ''} {p.retailer}" for p in products]
    return [e.tolist() for e in model.embed(texts)]


def ingest_to_qdrant(products: list[ScrapedProduct]):
    if not products:
        logger.info("No products to ingest")
        return

    logger.info(f"Ingesting {len(products)} products to Qdrant...")
    client = get_qdrant_client_from_env()
    vectors = embed_products(products)

    points = []
    for product, vector in zip(products, vectors):
        text = f"{product.name} {product.description or ''} {product.category or ''}"

        points.append(models.PointStruct(
            id=hashlib.md5(f"{product.retailer}:{product.name}:{product.price}".encode()).hexdigest(),
            vector={
                "dense": vector,
                "sparse": _sparse_vector(text),
            },
            payload={
                "retailer": product.retailer,
                "name": product.name,
                "price": product.price,
                "category": product.category,
                "discount_pct": product.discount_pct,
                "valid_from": product.valid_from.isoformat() if product.valid_from else None,
                "valid_to": product.valid_to.isoformat() if product.valid_to else None,
                "image_url": product.image_url,
                "source": "smartcart",
            },
        ))

    for i in range(0, len(points), 100):
        client.upsert(collection_name="products", points=points[i:i + 100])

    logger.info(f"Successfully ingested {len(points)} products")
