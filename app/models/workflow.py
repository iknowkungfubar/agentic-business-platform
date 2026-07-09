"""Workflow execution model — durable state for multi-agent DAG orchestration."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class WorkflowExecution(Base):
    """Persistent state for a multi-step DAG workflow execution.

    Enables crash recovery: after each node completes, the full state
    is saved. If the worker crashes, the orchestrator resumes from the
    last saved state.
    """

    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), default="")
    status = Column(String(50), default="PENDING")  # PENDING, RUNNING, HUMAN_IN_LOOP, COMPLETED, FAILED
    # JSON payload — stores DAG definition + node states
    state_payload = Column(Text, default="{}")
    current_node = Column(String(100), default="")
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
