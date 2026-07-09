"""TurinTech Agentic Business Platform — Enterprise API Server.

App factory: middleware, router inclusion, lifespan lifecycle.
Route handlers live in app/routers/ (one module per domain).
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import init_db
from app.middleware import RateLimiterMiddleware
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.eval import router as eval_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.mcp import router as mcp_router
from app.routers.policies import router as policies_router
from app.routers.sbom import router as sbom_router

_MAX_DB_RETRIES = 12
_DB_RETRY_DELAY = 2.5  # seconds


def _wait_for_db() -> None:
    """Retry connecting to the database with backoff.

    Handles the case where PostgreSQL isn't ready yet on first boot
    (docker-compose startup race).
    """
    import logging

    logger = logging.getLogger("turin-platform")
    for attempt in range(1, _MAX_DB_RETRIES + 1):
        try:
            from app.database import _get_engine  # noqa: PLC0415

            conn = _get_engine().connect()
            conn.execute(text("SELECT 1"))
            conn.close()
            logger.info("Database ready (attempt %d/%d)", attempt, _MAX_DB_RETRIES)
            return
        except Exception as exc:
            if attempt < _MAX_DB_RETRIES:
                logger.warning(
                    "Database not ready (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    _MAX_DB_RETRIES,
                    exc,
                    _DB_RETRY_DELAY,
                )
                time.sleep(_DB_RETRY_DELAY)
            else:
                logger.error(
                    "Database not reachable after %d attempts: %s",
                    _MAX_DB_RETRIES,
                    exc,
                )
                raise


def _run_migrations() -> None:
    """Run Alembic migrations, falling back to init_db() if not available."""
    import logging

    logger = logging.getLogger("turin-platform")
    try:
        from alembic import command  # noqa: PLC0415
        from alembic.config import Config  # noqa: PLC0415

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as exc:
        logger.warning("Alembic migration failed (%s), falling back to init_db()", exc)
        init_db()


@asynccontextmanager
async def lifespan(app: FastAPI, /) -> Any:
    """Application lifespan — startup and shutdown."""
    _wait_for_db()
    _run_migrations()
    yield


app = FastAPI(
    title="TurinTech Agentic Business Platform",
    version="0.1.0",
    description="Enterprise sovereign AI infrastructure for regulated industries",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware, max_requests=10, window_seconds=60)

# ── Routers ───────────────────────────────────────────────────────
# Health stays at root for k8s probes; everything else under /api/v1.
app.include_router(health_router, prefix="")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(eval_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(sbom_router, prefix="/api/v1")
