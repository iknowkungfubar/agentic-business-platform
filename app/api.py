"""TurinTech Agentic Business Platform — Enterprise API Server.

App factory: middleware, router inclusion, lifespan lifecycle.
Route handlers live in app/routers/ (one module per domain).
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import init_db
from app.routers.a2a import router as a2a_router
from app.routers.admin import router as admin_router
from app.routers.agents import router as agents_router
from app.routers.api_keys import router as api_keys_router
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.billing import router as billing_router
from app.routers.chat import router as chat_router
from app.routers.compliance import router as compliance_router
from app.routers.costs import router as costs_router
from app.routers.dashboard import router as dashboard_router
from app.routers.eval import router as eval_router
from app.routers.feedback import router as feedback_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.mcp import router as mcp_router
from app.routers.policies import router as policies_router
from app.routers.prompts import router as prompts_router
from app.routers.sbom import router as sbom_router
from app.routers.tenant import router as tenant_router
from app.routers.workflows import router as workflows_router
from app.ws import manager as ws_manager
from app.ws_voice import manager as voice_manager

from app.middleware import TokenBucketRateLimiter
from app.telemetry import (
    MetricsMiddleware,
    RequestIDMiddleware,
    get_logger,
    register_metrics_endpoint,
    setup_logging,
    setup_tracing,
)
from app.tenant import TenantContextMiddleware, TenantSessionFilter

setup_logging()
setup_tracing()
logger = get_logger("turin-platform")

_MAX_DB_RETRIES = 12
_DB_RETRY_DELAY = 2.5


def _wait_for_db() -> None:
    """Retry connecting to the database with backoff for PostgreSQL startup race."""
    for attempt in range(1, _MAX_DB_RETRIES + 1):
        try:
            from app.database import _get_write_engine as _get_engine  # noqa: PLC0415

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
    """Run Alembic migrations, falling back to init_db().

    Skips migration entirely if DISABLE_MIGRATIONS=true (used in tests
    where test_db fixture handles schema creation).
    """
    if os.environ.get("DISABLE_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        return
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
        "url": "https://turintechsolutions.com",
        "email": "josh@turintechsolutions.com",
    },
)

# ── Middleware stack ─────────────────────────────────────────────
# Order: RequestID → Tenant → Metrics → CORS → RateLimiter → app

app.add_middleware(RequestIDMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TokenBucketRateLimiter)

# ── Metrics endpoint (before routers) ────────────────────────────
register_metrics_endpoint(app)

# ── Error handlers ───────────────────────────────────────────────
from app.errors import register_error_handlers  # noqa: PLC0415

register_error_handlers(app)

# ── WebSocket endpoint ─────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time enterprise events.

    Connect with: ws://host:8000/ws?token=<jwt_token>
    """
    payload = await ws_manager.connect(websocket)
    if payload is None:
        return

    try:
        while True:
            # Keep connection alive — handle client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


@app.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for WebRTC voice signaling.

    Connect with: ws://host:8000/ws/voice?token=<jwt_token>
    Handles SDP offer/answer, ICE candidates, and audio data.
    """
    payload = await voice_manager.connect(websocket)
    if payload is None:
        return
    user_id = payload.get("user_id", 0)
    await voice_manager.run_signaling_loop(websocket, user_id)


# ── Routers ───────────────────────────────────────────────────────
# Health stays at root for k8s probes; everything else under /api/v1.
app.include_router(health_router, prefix="")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1/billing")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(eval_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1/feedback")
app.include_router(a2a_router, prefix="/api/v1/a2a")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1/agents")
app.include_router(api_keys_router, prefix="/api/v1/api-keys")
app.include_router(audit_router, prefix="/api/v1/audit")
app.include_router(compliance_router, prefix="/api/v1/compliance")
app.include_router(costs_router, prefix="/api/v1/costs")
app.include_router(dashboard_router, prefix="")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(prompts_router, prefix="/api/v1/prompts")
app.include_router(sbom_router, prefix="/api/v1")
app.include_router(tenant_router, prefix="")
app.include_router(workflows_router, prefix="")
