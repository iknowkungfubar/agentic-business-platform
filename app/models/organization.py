"""Organization model with SIEM webhook configuration."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # ── SIEM Webhook Configuration ───────────────────────────────
    siem_webhook_url = Column(String(512), default="")
    webhook_secret = Column(String(128), default="")

    users = relationship("User", back_populates="organization")
    agents = relationship("AgentRecord", back_populates="organization")
