"""Agent management endpoints — CRUD for agent records."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import AgentRecord, get_db
from app.pagination import PaginationParams, paginate
from app.routers import get_current_user, require_role

router = APIRouter(tags=["agents"])


class AgentCreateRequest(BaseModel):
    name: str
    url: str
    provider: str = "custom"
    tags: list[str] = []


@router.get("")
async def list_agents(
    page_params: PaginationParams = Depends(),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all agents visible to the user's organization (paginated)."""
    query = db.query(AgentRecord).filter(AgentRecord.organization_id == user.get("org_id")).order_by(AgentRecord.name)
    total = query.count()
    agents = query.offset(page_params.offset).limit(page_params.page_size).all()
    items = [
        {
            "id": a.id,
            "name": a.name,
            "url": a.url,
            "provider": a.provider,
            "status": a.status,
            "tags": a.tags,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
        }
        for a in agents
    ]
    return paginate(items, total, page_params)


@router.post("")
async def register_agent(
    req: AgentCreateRequest,
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    """Register a new agent."""
    agent = AgentRecord(
        name=req.name,
        url=req.url,
        provider=req.provider,
        tags=str(req.tags) if req.tags else "[]",
        status="unknown",
        organization_id=user.get("org_id"),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {
        "id": agent.id,
        "name": agent.name,
        "url": agent.url,
        "provider": agent.provider,
        "status": agent.status,
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get agent detail."""
    agent = (
        db.query(AgentRecord)
        .filter(
            AgentRecord.id == agent_id,
            AgentRecord.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "url": agent.url,
        "provider": agent.provider,
        "status": agent.status,
        "tags": agent.tags,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


@router.post("/{agent_id}/health")
async def check_agent_health(
    agent_id: int,
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    """Trigger a health check on an agent."""
    agent = (
        db.query(AgentRecord)
        .filter(
            AgentRecord.id == agent_id,
            AgentRecord.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    import httpx  # noqa: PLC0415

    try:
        resp = httpx.get(agent.url, timeout=5.0)
        agent.status = "healthy" if resp.status_code < 500 else "degraded"
    except Exception:
        agent.status = "unreachable"

    agent.last_seen = datetime.now(UTC)
    db.commit()
    return {"id": agent.id, "status": agent.status, "last_seen": agent.last_seen.isoformat()}
