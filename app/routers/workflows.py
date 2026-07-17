"""Workflow management endpoints — HITL approval and workflow monitoring."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.models import WorkflowExecution
from app.models.user import UserRole
from app.routers import RequireRole

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class ApprovalRequest(BaseModel):
    approval_token: str
    approved: bool = True


@router.post("/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: int,
    req: ApprovalRequest,
    user: Annotated[dict, Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve or reject a HITL workflow suspension.

    Validates the approval_token, verifies the user's RBAC role matches
    the required role, and pushes a resume event to Redis to wake the orchestrator.
    """
    wf = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.id == workflow_id,
            WorkflowExecution.organization_id == user.get("org_id"),
        )
        .first()
    )

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.status != "HUMAN_IN_LOOP":
        raise HTTPException(status_code=400, detail=f"Workflow is not awaiting human approval (status: {wf.status})")
    if wf.approval_token != req.approval_token:
        raise HTTPException(status_code=403, detail="Invalid approval token")

    # Check the user's role matches the required role
    required_role = wf.awaiting_approval_from_role
    if required_role and user.get("role", "") != required_role and user.get("role", "") != "superadmin":
        raise HTTPException(status_code=403, detail=f"Only {required_role} role can approve this step")

    if not req.approved:
        wf.status = "REJECTED"
        wf.error_message = f"Rejected by {user.get('sub', 'unknown')}"
        db.commit()
        return {"status": "REJECTED", "workflow_id": workflow_id}

    # Approve — push resume event to Redis
    import os

    from redis import Redis

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    try:
        r = Redis(host=redis_host, port=redis_port, db=0, socket_connect_timeout=2)
        r.publish("workflow:resume", json.dumps({"workflow_id": workflow_id, "approved_by": user.get("user_id")}))
        r.close()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to signal orchestrator: {exc}")

    wf.status = "RUNNING"
    wf.awaiting_approval_from_role = ""
    wf.approval_token = ""
    db.commit()

    return {"status": "RESUMED", "workflow_id": workflow_id}
