"""
Per-IP exponential backoff for ingest auth failures.

Makes brute-force of INGEST_API_KEY impractical: each failed attempt
increases the required wait before the next attempt for that IP.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

# Backoff: after n failures, block for base_sec * 2^min(n, max_exp)
DEFAULT_BASE_SEC = 60
DEFAULT_MAX_EXPONENT = 10
MAX_BACKOFF_SEC = 86400  # 24h cap


def _config_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return max(0, int(val))
    except ValueError:
        return default


class InMemoryIngestBackoff:
    """Tracks per-IP ingest auth failures and applies exponential backoff.

    Note: State is stored in memory, so this works for single-instance
    deployments only. In multi-instance or serverless environments,
    requests from the same IP can hit different instances and bypass
    backoff. For production-grade rate limiting across multiple instances,
    use a shared store like Redis.
    """

    __slots__ = ("_state", "_lock", "_base_sec", "_max_exp")

    def __init__(
        self,
        base_sec: int | None = None,
        max_exponent: int | None = None,
    ) -> None:
        # ip -> (fail_count, blocked_until)
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()
        self._base_sec = (
            base_sec
            if base_sec is not None
            else _config_int("INGEST_BACKOFF_BASE_SEC", DEFAULT_BASE_SEC)
        )
        self._max_exp = (
            max_exponent
            if max_exponent is not None
            else _config_int("INGEST_BACKOFF_MAX_EXPONENT", DEFAULT_MAX_EXPONENT)
        )

    def _backoff_seconds(self, fail_count: int) -> int:
        exp = min(fail_count, self._max_exp)
        return min(self._base_sec * (2**exp), MAX_BACKOFF_SEC)

    async def is_blocked(self, ip: str) -> tuple[bool, int]:
        """
        Return (blocked, retry_after_sec). retry_after_sec only if blocked.
        """
        now = time.monotonic()
        async with self._lock:
            entry = self._state.get(ip)
            if not entry:
                return False, 0
            _count, blocked_until = entry
            if now < blocked_until:
                return True, int(blocked_until - now + 0.5)
            return False, 0

    async def record_failure(self, ip: str) -> int:
        """
        Record a failed attempt for this IP; set blocked_until. Return retry_after_sec.
        """
        now = time.monotonic()
        async with self._lock:
            count, _ = self._state.get(ip, (0, 0.0))
            count += 1
            backoff = self._backoff_seconds(count)
            blocked_until = now + backoff
            self._state[ip] = (count, blocked_until)
            return backoff

    async def record_success(self, ip: str) -> None:
        """Clear failure state for this IP so legitimate callers are not penalized."""
        async with self._lock:
            self._state.pop(ip, None)


# Module-level singleton for use in auth dependency
_ingest_backoff: InMemoryIngestBackoff | None = None


def get_ingest_backoff() -> InMemoryIngestBackoff:
    global _ingest_backoff
    if _ingest_backoff is None:
        _ingest_backoff = InMemoryIngestBackoff()
    return _ingest_backoff
