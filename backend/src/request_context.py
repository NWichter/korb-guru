"""Request-scoped context (e.g. request_id) for logging and correlation."""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str:
    """Return current request_id or a placeholder."""
    return request_id_var.get() or "-"


def set_request_id(value: str | None) -> None:
    """Set request_id for the current context."""
    request_id_var.set(value)
