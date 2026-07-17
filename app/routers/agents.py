"""Agent management endpoints — ACP-powered agent registry.

Uses the Agent Control Plane's inventory module for agent CRUD.
Falls back to a simple file-based store when ACP is unavailable.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.pagination import Page, PaginationParams
from app.routers import get_current_user, require_role

router = APIRouter(tags=["agents"])


def _get_db_path() -> str:
    """Get ACP database path (env-overridable for tests)."""
    return os.getenv("ACP_DB_PATH", "/app/data/acp_inventory.db")


def _get_agents() -> list[dict[str, Any]]:
    """Get all agents from the ACP inventory database."""
    db_path = _get_db_path()
    try:
        import agent_control_plane.inventory as acp_inv

        conn = acp_inv.get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, url, provider, status, tags, created_at, last_seen FROM agents ORDER BY name")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in rows]
    except Exception:
        return _get_agents_fallback(db_path)


def _get_agents_fallback(db_path: str) -> list[dict[str, Any]]:
    """Fallback: return agents from a simple SQLite store."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS agents ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT, url TEXT, provider TEXT, status TEXT DEFAULT 'unknown', "
        "tags TEXT DEFAULT '[]', created_at TEXT, last_seen TEXT)"
    )
    cursor.execute("SELECT id, name, url, provider, status, tags, created_at, last_seen FROM agents ORDER BY name")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _add_agent(name: str, url: str, provider: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Register an agent in the ACP inventory database."""
    db_path = _get_db_path()
    now = datetime.now(UTC).isoformat()
    tags_json = json.dumps(tags or [])

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS agents ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT, url TEXT, provider TEXT, status TEXT DEFAULT 'unknown', "
            "tags TEXT DEFAULT '[]', created_at TEXT, last_seen TEXT)"
        )
        cursor.execute(
            "INSERT INTO agents (name, url, provider, status, tags, created_at, last_seen) VALUES (?, ?, ?, 'unknown', ?, ?, ?)",
            (name, url, provider, tags_json, now, now),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "name": name, "url": url, "provider": provider, "status": "unknown"}
    finally:
        conn.close()


def _update_agent_status(agent_id: int, status: str) -> None:
    """Update agent health status."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE agents SET status = ?, last_seen = ? WHERE id = ?",
            (status, datetime.now(UTC).isoformat(), agent_id),
        )
        conn.commit()
    finally:
        conn.close()


class AgentCreateRequest(BaseModel):
    name: str
    url: str
    provider: str = "custom"
    tags: list[str] = []


@router.get("")
async def list_agents(
    page_params: Annotated[PaginationParams, Depends()],
    user: Annotated[dict, Depends(get_current_user)],
):
    agents = _get_agents()
    offset = page_params.offset
    limit = page_params.page_size
    page_items = agents[offset : offset + limit] if offset < len(agents) else []
    return Page(
        items=page_items,
        total=len(agents),
        page=page_params.page,
        page_size=page_params.page_size,
        total_pages=max(1, (len(agents) + page_params.page_size - 1) // page_params.page_size),
    )


@router.post("")
async def register_agent(
    req: AgentCreateRequest,
    user: Annotated[dict, Depends(require_role("operator"))],
):
    try:
        return _add_agent(name=req.name, url=req.url, provider=req.provider, tags=req.tags)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to register agent: {exc}")


@router.get("/{agent_id}")
async def get_agent(
    agent_id: int,
    user: Annotated[dict, Depends(get_current_user)],
):
    agents = [a for a in _get_agents() if a.get("id") == agent_id]
    if not agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agents[0]


@router.post("/{agent_id}/health")
async def check_agent_health(
    agent_id: int,
    user: Annotated[dict, Depends(require_role("operator"))],
):
    import httpx

    agents = [a for a in _get_agents() if a.get("id") == agent_id]
    if not agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent_url = agents[0].get("url", "")
    if not agent_url:
        raise HTTPException(status_code=400, detail="Agent has no URL configured")

    try:
        resp = httpx.get(agent_url, timeout=5.0)
        status = "healthy" if resp.status_code < 500 else "degraded"
    except Exception:
        status = "unreachable"

    _update_agent_status(agent_id, status)
    return {"id": agent_id, "status": status, "last_seen": datetime.now(UTC).isoformat()}
