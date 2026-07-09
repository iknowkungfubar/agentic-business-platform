"""Event subscription model — webhook subscriptions for enterprise events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class EventSubscription(Base):
    """A webhook subscription for a specific enterprise event type."""

    __tablename__ = "event_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    # Event type to subscribe to (e.g. "chat.completed", "document.embedded", "*")
    event_type = Column(String(100), nullable=False)
    # Target URL for the webhook
    target_url = Column(String(512), nullable=False)
    # Optional HMAC secret for payload signing
    webhook_secret = Column(String(128), default="")
    # Whether this subscription is active
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    # Failure count for circuit breaking
    failure_count = Column(Integer, default=0)
    last_failure_at = Column(DateTime, nullable=True)
