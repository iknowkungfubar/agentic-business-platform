"""TurinTech Agentic Business Platform — Enterprise API Server.

App factory: middleware, router inclusion, startup.
Route handlers live in app/routers/ (one module per domain).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import RateLimiterMiddleware
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.mcp import router as mcp_router
from app.routers.sbom import router as sbom_router

app = FastAPI(
    title="TurinTech Agentic Business Platform",
    version="0.1.0",
    description="Enterprise sovereign AI infrastructure for regulated industries",
    docs_url="/docs",
    redoc_url="/redoc",
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

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(ingest_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(mcp_router)
app.include_router(sbom_router)


# ── Startup ──────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()
