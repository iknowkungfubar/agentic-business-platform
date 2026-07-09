"""Audit event model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    agent_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), default="")
    input_hash = Column(String(64), default="")
    output_hash = Column(String(64), default="")
    policy_decision = Column(String(50), default="")
    metadata_json = Column(Text, default="{}")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
