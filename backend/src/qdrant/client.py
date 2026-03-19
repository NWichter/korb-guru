"""Qdrant client singleton — lazy init from env settings."""

import logging
from pathlib import Path

# TODO: Replace sync QdrantClient with AsyncQdrantClient for production use.
# Kept synchronous for hackathon deadline — changing now is too risky.
from qdrant_client import QdrantClient

from ..config import get_settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    mode = settings.qdrant_mode
    logger.info("Initializing Qdrant client in '%s' mode", mode)

    if mode == "cloud":
        if not settings.qdrant_url or not settings.qdrant_api_key:
            raise ValueError("QDRANT_URL and QDRANT_API_KEY required for cloud mode")
        _client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    elif mode == "docker":
        _client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    elif mode == "local":
        _qdrant_data = Path(__file__).resolve().parent.parent.parent / "qdrant_data"
        _client = QdrantClient(path=str(_qdrant_data))
    elif mode == "memory":
        _client = QdrantClient(":memory:")
    else:
        raise ValueError(f"Unknown QDRANT_MODE: {mode}")

    logger.info("Qdrant client connected (%s)", mode)
    return _client
