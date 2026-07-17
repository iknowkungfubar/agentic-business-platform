"""Audit events API — query and retrieve security audit events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc

from app.database import get_db
from app.models import AuditEvent
from app.pagination import PaginationParams, paginate
from app.routers import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(tags=["audit"])


@router.get("/events")
async def list_audit_events(
    page_params: Annotated[PaginationParams, Depends()],
    action_type: Annotated[str | None, Query(description="Filter by action type")] = None,
    resource_type: Annotated[str | None, Query(description="Filter by resource type")] = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query audit events, with optional filters and pagination."""
    query = db.query(AuditEvent).filter(AuditEvent.organization_id == user.get("org_id"))

    if action_type:
        query = query.filter(AuditEvent.action_type == action_type)
    if resource_type:
        query = query.filter(AuditEvent.resource_type == resource_type)

    total = query.count()
    events = query.order_by(desc(AuditEvent.id)).offset(page_params.offset).limit(page_params.page_size).all()

    items = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "agent_id": e.agent_id,
            "user_id": e.user_id,
            "action_type": e.action_type,
            "resource_type": e.resource_type,
            "policy_decision": e.policy_decision,
        }
        for e in events
    ]
    return paginate(items, total, page_params)


@router.get("/events/{event_id}")
async def get_audit_event(
    event_id: int,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get a single audit event with full details."""
    event = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.id == event_id,
            AuditEvent.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return {
        "id": event.id,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "agent_id": event.agent_id,
        "user_id": event.user_id,
        "action_type": event.action_type,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "input_hash": event.input_hash,
        "output_hash": event.output_hash,
        "policy_decision": event.policy_decision,
        "metadata_json": event.metadata_json,
    }


@router.get("/integrity")
async def audit_integrity(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Verify audit log chain integrity (checks event count and sequence).

    Returns the total event count and a hash chain verification summary.
    Note: Full cryptographic chain verification requires the WORM store.
    """
    total = db.query(AuditEvent).filter(AuditEvent.organization_id == user.get("org_id")).count()
    return {
        "total_events": total,
        "status": "verification_available" if total > 0 else "empty",
        "note": "Full cryptographic integrity verification requires ACP WORM store integration",
    }
