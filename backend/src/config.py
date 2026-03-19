"""Application settings — reads from environment variables.

Qdrant and embedding configuration for vector search.
Database settings come from DATABASE_URL (handled in db.py).
Clerk auth settings come directly from env (handled in auth.py).
"""

import logging
from typing import Literal

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

# Native embedding dimensions per model.
# When using OpenAI, the API call truncates to the configured vector_size
# via the `dimensions` parameter (see embedding_service.py).
NATIVE_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
}

OPENAI_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class Settings(BaseSettings):
    # Qdrant
    qdrant_mode: Literal["local", "docker", "cloud", "memory"] = "docker"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # Embeddings
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    openai_api_key: str | None = None

    # LLM — Apify OpenRouter proxy (primary), direct OpenRouter (fallback)
    apify_token: str | None = None
    openrouter_api_key: str | None = None
    openrouter_default_model: str = "google/gemini-2.5-flash"

    # App
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}

    # Override this to request a specific output size from OpenAI's API.
    # Local models always use their native dimension.
    embedding_dimensions: int | None = None

    @property
    def vector_size(self) -> int:
        """Effective vector size for Qdrant collections.

        Local models always produce their native dimension.
        OpenAI models are truncated via the ``dimensions`` API param.
        Raises ValueError for unknown models to fail fast on misconfiguration.
        """
        if self.embedding_provider == "local":
            if self.embedding_model in OPENAI_EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Model {self.embedding_model!r} is an OpenAI model and cannot "
                    f"be used with provider='local'. Use provider='openai' or choose "
                    f"a local model: {list(NATIVE_EMBEDDING_DIMENSIONS.keys())}"
                )
            if self.embedding_model not in NATIVE_EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Unknown local embedding model: {self.embedding_model!r}. "
                    f"Supported models: {list(NATIVE_EMBEDDING_DIMENSIONS.keys())}"
                )
            return NATIVE_EMBEDDING_DIMENSIONS[self.embedding_model]
        # OpenAI: only text-embedding-3* models support the `dimensions` param
        if self.embedding_dimensions is not None:
            if self.embedding_model.startswith("text-embedding-3"):
                native = OPENAI_EMBEDDING_DIMENSIONS.get(self.embedding_model)
                if native is None:
                    known = [
                        k
                        for k in OPENAI_EMBEDDING_DIMENSIONS
                        if k.startswith("text-embedding-3")
                    ]
                    msg = f"Unknown model: {self.embedding_model!r}. Known: {known}"
                    raise ValueError(msg)
                if not (1 <= self.embedding_dimensions <= native):
                    raise ValueError(
                        f"embedding_dimensions must be "
                        f"between 1 and {native}, got "
                        f"{self.embedding_dimensions}"
                    )
                return self.embedding_dimensions
            _logger.warning(
                "embedding_dimensions is set but model %r does not support "
                "custom dimensions; using native dimension instead",
                self.embedding_model,
            )
        if self.embedding_model in OPENAI_EMBEDDING_DIMENSIONS:
            return OPENAI_EMBEDDING_DIMENSIONS[self.embedding_model]
        raise ValueError(
            f"Unknown embedding model: {self.embedding_model!r} and no "
            f"embedding_dimensions configured. Set EMBEDDING_DIMENSIONS or use "
            f"a known model: {list(OPENAI_EMBEDDING_DIMENSIONS.keys())}"
        )


def get_settings() -> Settings:
    """Lazy singleton for settings (avoids import-time .env reads in tests)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


_settings: Settings | None = None
