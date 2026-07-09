"""Cost tracking dashboard — real SQLAlchemy aggregate queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentRecord, Conversation, Message
from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


@router.get("")
async def cost_dashboard(
    period_days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get real infrastructure costs from message token usage, grouped by agent and time period."""
    cutoff = datetime.now(UTC) - timedelta(days=period_days)
    org_id = user.get("org_id")

    # Total token usage and estimated cost for the period
    usage_stats = (
        db.query(
            func.sum(Message.tokens_used).label("total_tokens"),
            func.count(Message.id).label("total_calls"),
            func.count(func.distinct(Message.model_tier)).label("model_count"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .first()
    ) or type("Row", (), {"total_tokens": 0, "total_calls": 0, "model_count": 0})()

    total_tokens = usage_stats.total_tokens or 0
    total_calls = usage_stats.total_calls or 0

    # Cost breakdown by model tier (estimated at $0.002/1K tokens for T1-T2, $0.008/1K for T3-T4)
    tier_costs: dict[str, dict[str, float | int]] = {}
    tier_query = (
        db.query(
            Message.model_tier,
            func.sum(Message.tokens_used).label("tokens"),
            func.count(Message.id).label("calls"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .group_by(Message.model_tier)
        .all()
    )

    for row in tier_query:
        tier = row.model_tier or "unknown"
        tokens = row.tokens or 0
        rate = 0.002 if tier in ("t1", "t2") else 0.008
        tier_costs[tier] = {
            "tokens": int(tokens),
            "calls": row.calls or 0,
            "estimated_cost": round(float(tokens) / 1000 * rate, 4),
        }

    # Cost by agent (via conversation linkage)
    agent_query = (
        db.query(
            AgentRecord.name,
            func.sum(Message.tokens_used).label("tokens"),
            func.count(Message.id).label("calls"),
        )
        .select_from(AgentRecord)
        .join(Conversation, Conversation.organization_id == AgentRecord.organization_id, isouter=True)
        .join(Message, Message.conversation_id == Conversation.id, isouter=True)
        .filter(AgentRecord.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .group_by(AgentRecord.name)
        .all()
    )

    by_agent = [
        {
            "agent": row.name,
            "tokens": int(row.tokens or 0),
            "calls": row.calls or 0,
        }
        for row in agent_query
    ]

    # Daily usage trend
    daily_query = (
        db.query(
            func.date(Message.created_at).label("day"),
            func.sum(Message.tokens_used).label("tokens"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
        .all()
    )

    by_day = [
        {
            "date": str(row.day),
            "tokens": int(row.tokens or 0),
        }
        for row in daily_query
    ]

    # Calculate overall estimated cost
    total_estimated_cost = sum(t["estimated_cost"] for t in tier_costs.values())

    return {
        "summary": {
            "period_days": period_days,
            "total_tokens": int(total_tokens),
            "total_api_calls": total_calls,
            "estimated_cost_usd": round(total_estimated_cost, 2),
        },
        "by_model_tier": tier_costs,
        "by_agent": by_agent,
        "daily_usage": by_day,
    }
