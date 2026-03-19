"""Qdrant vector database client and collection setup."""

from .client import get_qdrant_client
from .collections import init_collections

__all__ = ["get_qdrant_client", "init_collections"]
