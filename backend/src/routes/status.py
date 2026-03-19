"""System status endpoint — checks health of all external dependencies."""

import asyncio
import logging
import os
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db

router = APIRouter(tags=["status"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """Check health of all external services."""
    checks: dict[str, dict] = {}
    overall = "ok"

    # 1. PostgreSQL
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000
        checks["postgres"] = {"status": "ok", "latency_ms": round(latency_ms, 1)}
    except Exception as e:
        logger.warning("Postgres health check failed: %s", e)
        checks["postgres"] = {"status": "error", "error": "unavailable"}
        overall = "degraded"

    # 2. Qdrant
    try:
        from ..qdrant.client import get_qdrant_client

        start = time.perf_counter()
        client = get_qdrant_client()
        collections = (await asyncio.to_thread(client.get_collections)).collections
        latency_ms = (time.perf_counter() - start) * 1000
        checks["qdrant"] = {
            "status": "ok",
            "latency_ms": round(latency_ms, 1),
            "collections_count": len(collections),
        }
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", e)
        checks["qdrant"] = {"status": "error", "error": "unavailable"}
        overall = "degraded"

    # 3. OpenRouter LLM (optional — Apify-only is a valid config)
    api_key = os.getenv("OPENROUTER_API_KEY")
    checks["openrouter"] = {
        "status": "ok" if api_key else "not_configured",
        "configured": bool(api_key),
    }

    # 4. Apify
    apify_token = os.getenv("APIFY_TOKEN")
    checks["apify"] = {
        "status": "ok" if apify_token else "not_configured",
        "configured": bool(apify_token),
    }

    # Degrade only if neither LLM provider is configured
    if not api_key and not apify_token:
        overall = "degraded"

    # 5. Embedding service
    try:
        from ..config import get_settings

        s = get_settings()
        # Force vector_size computation to validate provider/model/dimensions
        _ = s.vector_size
        if s.embedding_provider == "openai" and not s.openai_api_key:
            checks["embeddings"] = {
                "status": "error",
                "error": "OPENAI_API_KEY not set",
            }
            overall = "degraded"
        else:
            checks["embeddings"] = {
                "status": "ok",
            }
    except Exception as e:
        logger.warning("Embeddings health check failed: %s", e)
        checks["embeddings"] = {"status": "error", "error": "unavailable"}
        overall = "degraded"

    body = {"status": overall, "checks": checks}
    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content=body, status_code=status_code)
