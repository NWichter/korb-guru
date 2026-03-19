"""
Authentication stubs — auth is disabled, all requests are allowed.
"""

from __future__ import annotations


class AuthUser:
    """Minimal user info."""

    def __init__(
        self,
        user_id: str = "dev_user",
        token_sub: str | None = "dev_user",
        session_id: str | None = None,
    ):
        self.user_id = user_id
        self.token_sub = token_sub
        self.session_id = session_id


async def require_clerk_auth() -> AuthUser:
    """No-op: always returns a dev user."""
    return AuthUser()


async def require_ingest_auth() -> None:
    """No-op: always allows ingest requests."""
    return None
