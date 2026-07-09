"""TurinTech Agentic Business Platform — Enterprise API Server.

App factory: middleware, router inclusion, lifespan lifecycle.
Route handlers live in app/routers/ (one module per domain).
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import init_db
from app.middleware import RateLimiterMiddleware
from app.routers.admin import router as admin_router
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.dashboard import router as dashboard_router
from app.routers.eval import router as eval_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.mcp import router as mcp_router
from app.routers.policies import router as policies_router
from app.routers.sbom import router as sbom_router

# ── Telemetry (structured logging, metrics) ──────────────────────
from app.telemetry import (
    MetricsMiddleware,
    RequestIDMiddleware,
    get_logger,
    register_metrics_endpoint,
    setup_logging,
)

setup_logging()
logger = get_logger("turin-platform")

_MAX_DB_RETRIES = 12
_DB_RETRY_DELAY = 2.5


def _wait_for_db() -> None:
    """Retry connecting to the database with backoff for PostgreSQL startup race."""
    for attempt in range(1, _MAX_DB_RETRIES + 1):
        try:
            from app.database import _get_engine  # noqa: PLC0415

            conn = _get_engine().connect()
            conn.execute(text("SELECT 1"))
            conn.close()
            logger.info("db_ready", extra={"attempt": attempt, "max_retries": _MAX_DB_RETRIES})
            return
        except Exception as exc:
            if attempt < _MAX_DB_RETRIES:
                logger.warning(
                    "db_not_ready",
                    extra={"attempt": attempt, "max_retries": _MAX_DB_RETRIES, "error": str(exc)},
                )
                time.sleep(_DB_RETRY_DELAY)
            else:
                logger.error(
                    "db_unreachable",
                    extra={"attempt": attempt, "max_retries": _MAX_DB_RETRIES, "error": str(exc)},
                )
                raise


def _run_migrations() -> None:
    """Run Alembic migrations, falling back to init_db()."""
    try:
        from alembic import command  # noqa: PLC0415
        from alembic.config import Config  # noqa: PLC0415

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("migrations_applied")
    except Exception as exc:
        logger.warning("migrations_failed", extra={"error": str(exc)})
        init_db()
        logger.info("init_db_fallback_complete")


@asynccontextmanager
async def lifespan(app: FastAPI, /) -> Any:
    """Application lifespan — startup and shutdown."""
    _wait_for_db()
    _run_migrations()
    logger.info("application_started", extra={"version": "0.1.0"})
    yield
    logger.info("application_shutdown")


# ── App Factory ──────────────────────────────────────────────────

app = FastAPI(
    title="TurinTech Agentic Business Platform",
    version="0.1.0",
    description="Enterprise sovereign AI infrastructure for regulated industries",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    contact={
        "name": "TurinTech Solutions",
        "url": "https://turintech.solutions",
        "email": "hello@turintech.solutions",
    },
)

# ── Middleware stack ─────────────────────────────────────────────
# Order: RequestID → Metrics → CORS → RateLimiter → app

app.add_middleware(RequestIDMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware, max_requests=int(os.getenv("RATE_LIMIT_MAX", "10")), window_seconds=60)

# ── Metrics endpoint (before routers) ────────────────────────────
register_metrics_endpoint(app)

# ── Error handlers ───────────────────────────────────────────────
from app.errors import register_error_handlers  # noqa: PLC0415

register_error_handlers(app)

# ── Routers ───────────────────────────────────────────────────────
# Health stays at root for k8s probes; everything else under /api/v1.
app.include_router(health_router, prefix="")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(eval_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1/agents")
app.include_router(dashboard_router, prefix="")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(sbom_router, prefix="/api/v1")
