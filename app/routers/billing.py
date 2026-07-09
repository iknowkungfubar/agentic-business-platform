"""Billing metering endpoints — usage aggregation and external billing sync."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Conversation, Message
from app.models.user import UserRole
from app.routers import RequireRole, get_current_user

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/usage")
async def get_usage(
    period_days: int = Query(30, ge=1, le=365),
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Get aggregated token usage for the organization over a period."""
    cutoff = datetime.now(UTC) - timedelta(days=period_days)
    org_id = user.get("org_id")

    totals = (
        db.query(
            func.sum(Message.tokens_used).label("total_tokens"),
            func.count(Message.id).label("total_calls"),
            func.count(func.distinct(Message.model_tier)).label("tiers_used"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .first()
    )

    daily = (
        db.query(
            func.date(Message.created_at).label("day"),
            func.sum(Message.tokens_used).label("tokens"),
            func.count(Message.id).label("calls"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == org_id)
        .filter(Message.created_at >= cutoff)
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
        .all()
    )

    return {
        "organization_id": org_id,
        "period_days": period_days,
        "totals": {
            "tokens": int(getattr(totals, "total_tokens", 0) or 0),
            "calls": int(getattr(totals, "total_calls", 0) or 0),
            "tiers": int(getattr(totals, "tiers_used", 0) or 0),
        },
        "daily_breakdown": [
            {
                "date": str(row.day),
                "tokens": int(row.tokens or 0),
                "calls": int(row.calls or 0),
            }
            for row in daily
        ],
    }
