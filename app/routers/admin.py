"""Admin endpoints — users, agents, audit log."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentRecord, AuditEvent, User
from app.routers import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = db.query(User).filter(User.organization_id == user.get("org_id")).all()
    return [{"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name} for u in users]


@router.get("/agents")
async def list_agents(
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    agents = db.query(AgentRecord).filter(AgentRecord.organization_id == user.get("org_id")).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "url": a.url,
            "provider": a.provider,
            "status": a.status,
        }
        for a in agents
    ]


@router.get("/audit-log")
async def audit_log(
    limit: int = 50,
    user: dict = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.organization_id == user.get("org_id"))
        .order_by(AuditEvent.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "agent_id": e.agent_id,
            "action_type": e.action_type,
            "policy_decision": e.policy_decision,
        }
        for e in events
    ]
