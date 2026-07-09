"""Organization model with SIEM webhook + white-label branding configuration."""

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

    # ── SIEM Webhook ─────────────────────────────────────────────
    siem_webhook_url = Column(String(512), default="")
    webhook_secret = Column(String(128), default="")

    # ── White-label Branding ──────────────────────────────────────
    custom_domain = Column(String(255), default="", index=True)
    logo_url = Column(String(512), default="")
    primary_color_hex = Column(String(7), default="#10b981")  # emerald-500
    secondary_color_hex = Column(String(7), default="#6366f1")  # indigo-500

    users = relationship("User", back_populates="organization")
    agents = relationship("AgentRecord", back_populates="organization")
