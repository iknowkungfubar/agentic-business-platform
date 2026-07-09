"""Cost tracking dashboard endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


@router.get("")
async def cost_dashboard(user: dict = Depends(get_current_user)):
    """Get cost dashboard by agent, model, and department.

    Returns mock data when ACP cost tracker is not integrated.
    For production, install ACP and use agent_control_plane.cost_tracker.
    """
    return {
        "summary": {
            "total_cost": 0.0,
            "period": "current_month",
            "currency": "USD",
        },
        "by_agent": [],
        "by_model": [],
        "by_department": [],
        "note": "Cost tracking requires ACP integration. Install agent-control-plane and configure cost_tracker.",
        "integration": "https://github.com/iknowkungfubar/agent-control-plane",
    }
