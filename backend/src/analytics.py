"""
PostHog analytics for the API: security/audit and product events.

Use for events you want in PostHog alongside mobile analytics (e.g. ingest auth
failures, blocked IPs). Python logging remains for stdout and ops; PostHog
gives a single place to see security events and correlate with frontend.
"""

from __future__ import annotations

import os
from typing import Any

_posthog: Any = None

# Same project as mobile; server uses POSTHOG_API_KEY (not exposed to client)
_POSTHOG_KEY_ENV = "POSTHOG_API_KEY"
_POSTHOG_HOST_ENV = "POSTHOG_HOST"
_DEFAULT_HOST = "https://app.posthog.com"


def _get_client() -> Any:
    global _posthog
    if _posthog is not None:
        return _posthog
    key = os.getenv(_POSTHOG_KEY_ENV) or ""
    if not key or key.startswith("phc_placeholder") or key == "phc_your_":
        return None
    try:
        from posthog import Posthog

        host = os.getenv(_POSTHOG_HOST_ENV) or _DEFAULT_HOST
        _posthog = Posthog(project_api_key=key, host=host)
        return _posthog
    except Exception:
        return None


def capture(
    event: str,
    distinct_id: str = "api",
    properties: dict[str, Any] | None = None,
    *,
    process_person_profile: bool = False,
) -> None:
    """
    Send an event to PostHog. No-op if key unset or placeholder.
    Server events use distinct_id='api' and no person profile by default.
    """
    client = _get_client()
    if not client:
        return
    props = dict(properties or {})
    if not process_person_profile:
        props["$process_person_profile"] = False
    try:
        client.capture(event, distinct_id=distinct_id, properties=props)
    except Exception:
        pass


def flush() -> None:
    """Flush queued events. Call after request in middleware."""
    client = _get_client()
    if client:
        try:
            client.flush()
        except Exception:
            pass


def capture_ingest_auth_failure(client_ip: str, retry_after_sec: int) -> None:
    """Emit ingest auth failure for security visibility in PostHog."""
    capture(
        "ingest_auth_failure",
        distinct_id="api",
        properties={
            "client_ip": client_ip,
            "retry_after_sec": retry_after_sec,
            "source": "api",
        },
    )


def capture_ingest_auth_blocked(client_ip: str, retry_after: int) -> None:
    """Emit ingest auth blocked (rate limit) for security visibility."""
    capture(
        "ingest_auth_blocked",
        distinct_id="api",
        properties={
            "client_ip": client_ip,
            "retry_after": retry_after,
            "source": "api",
        },
    )
