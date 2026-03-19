"""Initialize Qdrant collections: products, recipes, user_preferences."""

import logging

from qdrant_client import models

from ..config import get_settings
from .client import get_qdrant_client

logger = logging.getLogger(__name__)


def _create_collection_safe(client, name: str, **kwargs) -> None:
    """Create a single collection, skipping if it already exists."""
    try:
        client.create_collection(collection_name=name, **kwargs)
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info("Collection %r already exists, skipping", name)
            return
        raise


def init_collections() -> None:
    settings = get_settings()
    vector_size = settings.vector_size
    client = get_qdrant_client()

    # 1. Products — hybrid search with dense + sparse vectors
    _create_collection_safe(
        client,
        "products",
        vectors_config={
            "dense": models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            ),
        ),
    )
    for field, schema in [
        ("retailer", models.PayloadSchemaType.KEYWORD),
        ("category", models.PayloadSchemaType.KEYWORD),
        ("region", models.PayloadSchemaType.KEYWORD),
        ("price", models.PayloadSchemaType.FLOAT),
        ("discount_pct", models.PayloadSchemaType.FLOAT),
        ("valid_to", models.PayloadSchemaType.DATETIME),
    ]:
        try:
            client.create_payload_index("products", field, field_schema=schema)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
    logger.info("'products' collection ready")

    # 2. Recipes — dense vector search
    _create_collection_safe(
        client,
        "recipes",
        vectors_config=models.VectorParams(
            size=vector_size, distance=models.Distance.COSINE
        ),
    )
    for field, schema in [
        ("type", models.PayloadSchemaType.KEYWORD),
        ("cost", models.PayloadSchemaType.FLOAT),
        ("time_minutes", models.PayloadSchemaType.INTEGER),
        ("household_id", models.PayloadSchemaType.KEYWORD),
    ]:
        try:
            client.create_payload_index("recipes", field, field_schema=schema)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
    logger.info("'recipes' collection ready")

    # 3. User preferences — Discovery API
    # Contains both recipe and product preference vectors.
    # Use the "domain" payload field ("recipe" | "product") to distinguish them.
    _create_collection_safe(
        client,
        "user_preferences",
        vectors_config=models.VectorParams(
            size=vector_size, distance=models.Distance.COSINE
        ),
    )
    for field in ["user_id", "household_id", "domain"]:
        try:
            client.create_payload_index(
                "user_preferences",
                field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
    logger.info("'user_preferences' collection ready")

    logger.info("All Qdrant collections initialized")
