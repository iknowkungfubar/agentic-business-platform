"""Policy management endpoints — list and test compliance policies."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers import get_current_user

router = APIRouter(tags=["policies"])


class PolicyTestRequest(BaseModel):
    action: dict


@router.get("/policies")
async def list_policies(user: dict = Depends(get_current_user)):
    """List all available compliance policy templates."""
    from core.governance.templates import PolicyTemplates  # noqa: PLC0415

    cmmc = PolicyTemplates.get_cmmc_rules()
    return {
        "frameworks": ["cmmc"],
        "policies": [
            {
                "name": r.name,
                "description": r.description,
                "effect": r.effect.value,
                "framework": "cmmc",
            }
            for r in cmmc
        ],
        "total": len(cmmc),
    }


@router.post("/test-policy")
async def test_policy(req: PolicyTestRequest, user: dict = Depends(get_current_user)):
    """Test an action against the CMMC policy set."""
    from core.governance.policy import PolicyEngine  # noqa: PLC0415
    from core.governance.templates import PolicyTemplates  # noqa: PLC0415

    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())
    result = engine.evaluate(req.action)
    return {
        "effect": result.effect.value,
        "matched_rule": result.matched_rule,
        "matched_rules": result.matched_rules,
        "details": result.details,
    }
