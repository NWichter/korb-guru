"""Embedding service — local (fastembed) or OpenAI text embeddings."""

import asyncio
import logging
from functools import lru_cache

from ..config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_fastembed_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=get_settings().embedding_model)


def _embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Synchronous embedding implementation."""
    settings = get_settings()
    if settings.embedding_provider == "local":
        model = _get_fastembed_model()
        embeddings = list(model.embed(texts))
        return [e.tolist() for e in embeddings]
    elif settings.embedding_provider == "openai":
        import httpx

        model_name = (
            settings.embedding_model
            if settings.embedding_model.startswith("text-embedding")
            else "text-embedding-3-small"
        )
        body: dict = {
            "model": model_name,
            "input": texts,
        }
        is_v3 = model_name.startswith("text-embedding-3")
        if is_v3 and settings.embedding_provider == "openai":
            body["dimensions"] = settings.vector_size

        with httpx.Client(timeout=30.0) as http_client:
            resp = http_client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=body,
            )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]
    else:
        msg = f"Unknown embedding provider: {settings.embedding_provider}"
        raise ValueError(msg)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts. Safe to call from sync context."""
    try:
        return _embed_texts_sync(texts)
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        raise


async def embed_texts_async(texts: list[str]) -> list[list[float]]:
    """Async-safe embedding — runs blocking work in a thread."""
    try:
        return await asyncio.to_thread(_embed_texts_sync, texts)
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        raise


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


async def embed_text_async(text: str) -> list[float]:
    result = await embed_texts_async([text])
    return result[0]
