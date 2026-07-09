"""Admin endpoints — users, agents, audit log, GDPR compliance."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Organization, User as UserModel
from app.models import AgentRecord, AuditEvent
from app.models.user import UserRole
from app.routers import RequireRole, get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    user: dict = Depends(RequireRole(UserRole.SUPERADMIN, UserRole.ORG_ADMIN)),
    db: Session = Depends(get_db),
):
    """List all users in the organization (excluding soft-deleted)."""
    users = (
        db.query(UserModel)
        .filter(
            UserModel.organization_id == user.get("org_id"),
            UserModel.deleted_at.is_(None),
        )
        .all()
    )
    return [{"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name} for u in users]


@router.delete("/users/{user_id}/forget")
async def forget_user(
    user_id: int,
    user: dict = Depends(RequireRole(UserRole.SUPERADMIN, UserRole.ORG_ADMIN)),
    db: Session = Depends(get_db),
):
    """GDPR Right to be Forgotten — anonymize user data while preserving WORM audit integrity.

    Overwrites PII fields with SHA-256 hashes, sets deleted_at, and preserves
    primary keys so AuditEvent foreign key relationships remain intact.
    """
    target = (
        db.query(UserModel)
        .filter(
            UserModel.id == user_id,
            UserModel.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.deleted_at:
        raise HTTPException(status_code=400, detail="User already forgotten")

    # Anonymize — hash PII fields with a salt to prevent reversal
    salt = hashlib.sha256(f"{user_id}-{datetime.now(UTC).isoformat()}".encode()).hexdigest()[:16]
    target.email = hashlib.sha256(f"{target.email}--{salt}".encode()).hexdigest()[:32] + "@anonymized.local"
    target.full_name = f"User_{target.id}_anonymized"
    target.hashed_password = hashlib.sha256(f"DELETED-{salt}".encode()).hexdigest()
    target.deleted_at = datetime.now(UTC)

    db.commit()
    return {"status": "anonymized", "user_id": user_id}


@router.get("/agents")
async def list_agents(
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN)),
    db: Session = Depends(get_db),
):
    """List all agents in the organization."""
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
    user: dict = Depends(RequireRole(UserRole.AUDITOR, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Query audit events for the organization (WORM-protected, cannot be modified)."""
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
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "agent_id": e.agent_id,
            "action_type": e.action_type,
            "policy_decision": e.policy_decision,
        }
        for e in events
    ]


@router.post("/organizations/{org_id}/legal-hold")
async def toggle_legal_hold(
    org_id: int,
    under_hold: bool = True,
    user: dict = Depends(RequireRole(UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Toggle legal hold for an organization (SUPERADMIN only).

    When under legal hold, the data retention cron will skip permanent
    deletion of this organization's records, preserving WORM audit logs
    and chat histories during litigation.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.under_legal_hold = 1 if under_hold else 0
    db.commit()
    return {"organization_id": org_id, "under_legal_hold": under_hold}
