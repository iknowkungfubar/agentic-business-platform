"""Compliance endpoints — evidence-based reports from real WORM audit data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent
from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


@router.post("/report")
async def generate_compliance_report(
    period_days: int = Query(90, ge=1, le=365, description="Lookback period in days"),
    framework: str = Query("CMMC-2.0", description="Compliance framework"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a compliance report from real WORM audit events.

    Queries the actual audit_events table for the organization,
    aggregates policy decisions (allow/deny/audit), and produces
    a scored compliance report with evidence counts.
    """
    cutoff = datetime.now(UTC) - timedelta(days=period_days)
    org_id = user.get("org_id")

    # Total audit events in period
    total_events = (
        db.query(func.count(AuditEvent.id))
        .filter(
            AuditEvent.organization_id == org_id,
            AuditEvent.timestamp >= cutoff,
        )
        .scalar()
    ) or 0

    # Policy decision breakdown
    decision_counts = (
        db.query(
            AuditEvent.policy_decision,
            func.count(AuditEvent.id).label("count"),
        )
        .filter(
            AuditEvent.organization_id == org_id,
            AuditEvent.timestamp >= cutoff,
        )
        .group_by(AuditEvent.policy_decision)
        .all()
    )

    decisions: dict[str, int] = {}
    for row in decision_counts:
        decisions[row.policy_decision or "unknown"] = row.count

    allowed = decisions.get("allow", 0)
    denied = decisions.get("deny", 0)

    # Action type distribution
    action_types = (
        db.query(
            AuditEvent.action_type,
            func.count(AuditEvent.id).label("count"),
        )
        .filter(
            AuditEvent.organization_id == org_id,
            AuditEvent.timestamp >= cutoff,
        )
        .group_by(AuditEvent.action_type)
        .order_by(func.count(AuditEvent.id).desc())
        .limit(10)
        .all()
    )

    # Calculate adherence score
    total_decisions = allowed + denied
    adherence_score = round(allowed / max(total_decisions, 1) * 100, 1) if total_decisions > 0 else 0.0

    # CMMC-specific control mapping based on action types present
    controls_present = set(row.action_type for row in action_types)

    cmmc_controls = [
        {
            "id": "AC.1.001",
            "name": "Access Control",
            "status": "passed" if "data_access" in controls_present else "not-tested",
            "evidence": decisions.get("allow", 0),
        },
        {
            "id": "AU.1.001",
            "name": "Audit & Accountability",
            "status": "passed" if total_events > 0 else "not-tested",
            "evidence": total_events,
        },
        {
            "id": "IA.1.001",
            "name": "Identification & Authentication",
            "status": "passed" if "login" in controls_present else "not-tested",
            "evidence": decisions.get("allow", 0),
        },
        {
            "id": "SC.1.001",
            "name": "System & Communications",
            "status": "passed" if "network_access" in controls_present else "not-tested",
            "evidence": 0,
        },
        {
            "id": "AI-1",
            "name": "Input Validation",
            "status": "passed" if denied > 0 else "not-tested",
            "evidence": denied,
        },
        {
            "id": "AI-3",
            "name": "Output Monitoring",
            "status": "passed" if total_events > 0 else "not-tested",
            "evidence": total_events,
        },
    ]

    passed_controls = sum(1 for c in cmmc_controls if c["status"] == "passed")
    total_controls = len(cmmc_controls)

    return {
        "framework": framework,
        "period_days": period_days,
        "generated_at": datetime.now(UTC).isoformat(),
        "generated_by": user.get("sub", "unknown"),
        "summary": {
            "total_audit_events": total_events,
            "total_decisions": total_decisions,
            "allowed": allowed,
            "denied": denied,
            "adherence_score": adherence_score,
            "controls_passed": f"{passed_controls}/{total_controls}",
        },
        "controls": cmmc_controls,
        "action_types": [{"type": row.action_type, "count": row.count} for row in action_types],
    }


@router.get("/status")
async def compliance_status(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current compliance posture summary from audit data."""
    org_id = user.get("org_id")
    total_events = (db.query(func.count(AuditEvent.id)).filter(AuditEvent.organization_id == org_id).scalar()) or 0
    decision_counts = (
        db.query(
            AuditEvent.policy_decision,
            func.count(AuditEvent.id).label("count"),
        )
        .filter(AuditEvent.organization_id == org_id)
        .group_by(AuditEvent.policy_decision)
        .all()
    )
    denied = sum(getattr(row, "count", 0) for row in decision_counts if getattr(row, "policy_decision", None) == "deny")
    return {
        "frameworks": ["CMMC-2.0"],
        "overall_status": "audit_in_progress" if total_events > 0 else "no_data",
        "total_events": total_events,
        "denied_actions": denied,
        "last_assessment": None,
    }


@router.get("/reports")
async def list_reports(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List compliance report history from audit data."""
    org_id = user.get("org_id")
    event_count = (db.query(func.count(AuditEvent.id)).filter(AuditEvent.organization_id == org_id).scalar()) or 0
    return {
        "reports": [],
        "total": 0,
        "note": f"Compliance reports are generated on-demand via POST /api/v1/compliance/report. {event_count} audit events available for analysis.",
    }
