"""Health check endpoints — liveness, readiness, and deep health probes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness():
    """Liveness probe — returns 200 if the process is alive.

    Used by Kubernetes livenessProbe. Does NOT check dependencies
    so a transient DB blip doesn't kill the pod.
    """
    return {"status": "ok", "version": "0.1.0", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — returns 200 when the service can accept traffic.

    Checks database connectivity. Used by Kubernetes readinessProbe.
    """
    from app.database import _get_write_engine as _get_engine

    try:
        conn = _get_engine().connect()
        conn.execute(text("SELECT 1"))
        conn.close()
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "database": "disconnected",
                "error": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )


@router.get("/health/deep")
async def deep_health():
    """Deep health probe — comprehensive system check.

    Checks database, migrations status, and downstream services.
    Used by monitoring dashboards and alerting.
    """
    from app.database import _get_write_engine as _get_engine

    checks = {
        "database": False,
        "migrations": False,
        "inference": False,
    }

    try:
        conn = _get_engine().connect()
        conn.execute(text("SELECT 1"))

        # Check if alembic has been applied
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        conn.close()
        checks["database"] = True
        checks["migrations"] = version is not None
    except Exception:
        checks["database"] = False

    # Check inference connectivity (non-blocking)
    import httpx

    from app.config import settings

    try:
        resp = httpx.get(f"{settings.inference_url}/models", timeout=2.0)
        checks["inference"] = resp.status_code == 200
    except Exception:
        checks["inference"] = False

    all_ok = all(checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_ok else "degraded",
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
