import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load root .env when running standalone (e.g. cd apps/api && uv run uvicorn).
# Via pnpm dev from root, dotenv-cli injects env; this is a fallback.
_repo_root = Path(__file__).resolve().parent.parent.parent.parent
_root_env = _repo_root / ".env"
if _root_env.is_file():
    load_dotenv(_root_env, override=False)

# Imports below must run after env load so pydantic-settings and others see root .env.
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from .analytics import flush as posthog_flush  # noqa: E402
from .logging_config import configure_logging  # noqa: E402
from .request_context import set_request_id  # noqa: E402
from .routes import (  # noqa: E402
    admin_router,
    budget_router,
    examples_router,
    grocery_router,
    health_router,
    hello_router,
    households_router,
    ingest_router,
    me_router,
    meal_plans_router,
    messages_router,
    notifications_router,
    polls_router,
    products_router,
    receipts_router,
    recipes_router,
    route_router,
    status_router,
    stores_router,
)

configure_logging()
_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize Qdrant collections. Shutdown: cleanup."""
    try:
        from .qdrant.collections import init_collections

        init_collections()
        _logger.info("Qdrant collections initialized")
    except Exception as e:
        err_msg = str(e).lower()
        conn_err = "connection" in err_msg or "connect" in err_msg
        if conn_err or "name resolution" in err_msg:
            _logger.warning("Qdrant init skipped (not connected): %s", e)
        else:
            _logger.error("Qdrant init failed: %s", e)
            raise
    yield


app = FastAPI(
    title="Korb API",
    description="Backend API for Korb meal planning application",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: origins from CORS_ORIGINS env (comma-separated). Empty/unset = no origins.
_origins_raw = (os.getenv("CORS_ORIGINS") or "").strip()
_cors_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Legacy routes (kept for backward compatibility) ──────────
app.include_router(health_router)
# NOTE: /status exposes internal service details (collection names, latencies).
# This is intentional for dev/hackathon use. In production, protect this route
# behind authentication or restrict access via reverse proxy rules.
app.include_router(status_router)
app.include_router(hello_router)
app.include_router(examples_router)
app.include_router(ingest_router)

# ── Integrated backend routes (Clerk auth, /api/v1/ prefix) ──
app.include_router(me_router)
app.include_router(households_router)
app.include_router(recipes_router)
app.include_router(meal_plans_router)
app.include_router(grocery_router)
app.include_router(budget_router)
app.include_router(products_router)
app.include_router(messages_router)
app.include_router(polls_router)
app.include_router(notifications_router)
app.include_router(route_router)
app.include_router(stores_router)
app.include_router(receipts_router)

# ── Admin routes (no auth, dev only) ──
if os.getenv("AUTH_DEV_MODE", "").lower() == "true":
    app.include_router(admin_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Return stable JSON 500 without leaking stack traces to the client."""
    _logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate or forward X-Request-ID and set in context for logging."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """Log request method, path, status, duration (PII-safe: no body or auth)."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    _logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.middleware("http")
async def flush_posthog(request: Request, call_next):
    """Flush PostHog after each request so events are sent (e.g. in serverless)."""
    response = await call_next(request)
    posthog_flush()
    return response
