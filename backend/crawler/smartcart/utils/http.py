"""HTTP client with retry logic and per-domain rate limiting."""
import asyncio
import logging
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx

from crawler.smartcart.config import DEFAULT_HEADERS, RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None

# Per-domain rate limiting state
_domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_last_request_time: dict[str, float] = defaultdict(float)


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True)
    return _client


async def _rate_limit(url: str) -> None:
    """Enforce minimum delay between requests to the same domain."""
    domain = urlparse(url).netloc
    async with _domain_locks[domain]:
        now = time.monotonic()
        elapsed = now - _last_request_time[domain]
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        _last_request_time[domain] = time.monotonic()


async def fetch_with_retry(url: str, retries: int = 3, **kwargs) -> httpx.Response:
    client = get_client()
    for attempt in range(1, retries + 1):
        await _rate_limit(url)
        try:
            resp = await client.get(url, **kwargs)
            if resp.status_code == 404:
                return resp
            if resp.is_success:
                return resp
            if attempt == retries:
                return resp
        except Exception:
            if attempt == retries:
                raise
        await asyncio.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"Failed to fetch {url}")


async def fetch_text(url: str, **kwargs) -> str:
    resp = await fetch_with_retry(url, **kwargs)
    resp.raise_for_status()
    return resp.text


async def fetch_json(url: str, **kwargs) -> dict:
    resp = await fetch_with_retry(url, **kwargs)
    resp.raise_for_status()
    return resp.json()


async def fetch_bytes(url: str, **kwargs) -> bytes:
    resp = await fetch_with_retry(url, **kwargs)
    resp.raise_for_status()
    return resp.content


async def head_check(url: str) -> bool:
    client = get_client()
    try:
        resp = await client.head(url)
        return resp.is_success
    except Exception:
        return False


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
