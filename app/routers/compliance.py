"""Compliance endpoints — generate compliance reports and check status."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


class ComplianceReportRequest(BaseModel):
    framework: str = "CMMC-2.0"


@router.post("/report")
async def generate_compliance_report(
    req: ComplianceReportRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a compliance report for the specified framework."""
    from core.governance.policy import PolicyEngine  # noqa: PLC0415
    from core.governance.templates import PolicyTemplates  # noqa: PLC0415

    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())

    # Evaluate each rule against a set of sample action types
    frameworks = {
        "CMMC-2.0": PolicyTemplates.get_cmmc_rules,
    }

    rules = frameworks.get(req.framework, frameworks["CMMC-2.0"])()
    controls = []
    passed = 0
    failed = 0

    for rule in rules:
        # For each rule, evaluate against a standard action template
        action = {
            "action_type": "data_access",
            "resource_type": "cui",
            "requires_auth": True,
            "authenticated": True,
            "requires_input_validation": rule.conditions.get("requires_input_validation", False),
            "input_validated": True,
        }
        result = engine.evaluate(action)

        status = (
            "passed" if result.effect.value == "allow" else "failed" if result.effect.value == "deny" else "not-tested"
        )
        if status == "passed":
            passed += 1
        else:
            failed += 1

        controls.append(
            {
                "id": rule.name,
                "name": rule.description[:80],
                "status": status,
                "effect": result.effect.value,
            }
        )

    return {
        "framework": req.framework,
        "generated_at": datetime.now(UTC).isoformat(),
        "generated_by": user.get("sub", "unknown"),
        "summary": {
            "total": len(controls),
            "passed": passed,
            "failed": failed,
            "score": round(passed / max(len(controls), 1) * 100, 1),
        },
        "controls": controls,
    }


@router.get("/status")
async def compliance_status(user: dict = Depends(get_current_user)):
    """Get current compliance posture summary."""
    return {
        "frameworks": ["CMMC-2.0"],
        "overall_status": "needs_assessment",
        "last_assessment": None,
        "note": "Run POST /api/v1/compliance/report to generate a full assessment",
    }


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    """List generated compliance reports (placeholder — persistence TBD)."""
    return {
        "reports": [],
        "total": 0,
        "note": "Compliance report persistence requires ACP integration",
    }
