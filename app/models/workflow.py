"""Workflow execution model — durable state for multi-agent DAG orchestration with HITL support."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), default="")
    status = Column(String(50), default="PENDING")  # PENDING, RUNNING, HUMAN_IN_LOOP, COMPLETED, FAILED
    state_payload = Column(Text, default="{}")
    current_node = Column(String(100), default="")
    error_message = Column(Text, default="")

    # ── HITL (Human-in-the-Loop) ────────────────────────────────
    awaiting_approval_from_role = Column(String(50), default="")
    approval_token = Column(String(64), default="")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
