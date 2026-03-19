"""Structured logging: request_id filter and consistent format."""

from __future__ import annotations

import logging
import os

from .request_context import get_request_id


class RequestIdFilter(logging.Filter):
    """Add request_id to every log record for correlation."""

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "request_id", get_request_id())
        return True


def configure_logging() -> None:
    """Configure root logger with request_id and timestamp."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    fmt = "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    for handler in logging.root.handlers:
        handler.addFilter(RequestIdFilter())
