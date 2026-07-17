"""Audit event model with WORM cryptographic chaining.

Each event's signature is a SHA-256 hash of its own JSON payload
concatenated with the previous event's signature, forming a
tamper-evident chain. Modifying any event breaks the chain for
all subsequent events.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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

    # ── WORM Chain Fields ──────────────────────────────────────
    # SHA-256 hash of this event's payload
    signature = Column(String(64), default="")
    # Signature of the chronologically previous event in this org's chain
    prev_event_signature = Column(String(64), default="")


def compute_event_payload(event: AuditEvent) -> dict[str, Any]:
    """Compute the canonical payload dict for signing."""
    return {
        "timestamp": event.timestamp.isoformat() if event.timestamp else "",
        "agent_id": event.agent_id,
        "user_id": event.user_id,
        "action_type": event.action_type,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id or "",
        "input_hash": event.input_hash or "",
        "output_hash": event.output_hash or "",
        "policy_decision": event.policy_decision or "",
        "metadata_json": event.metadata_json or "{}",
        "organization_id": event.organization_id,
    }


def compute_signature(payload: dict[str, Any], prev_signature: str = "") -> str:
    """Compute SHA-256 hash of payload + previous signature."""
    raw = json.dumps(payload, sort_keys=True, default=str) + prev_signature
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_audit_event(
    db: Session,
    agent_id: str,
    user_id: str,
    action_type: str,
    resource_type: str,
    resource_id: str = "",
    input_hash: str = "",
    output_hash: str = "",
    policy_decision: str = "",
    metadata_json: str = "{}",
    organization_id: int | None = None,
) -> AuditEvent:
    """Create a new audit event with proper WORM chaining.

    Automatically computes the signature and links to the previous
    event in the chain for the same organization.
    """
    event = AuditEvent(
        timestamp=datetime.now(UTC),
        agent_id=agent_id,
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        input_hash=input_hash,
        output_hash=output_hash,
        policy_decision=policy_decision,
        metadata_json=metadata_json,
        organization_id=organization_id,
    )

    # Get the previous event's signature for chain linking
    prev_event = (
        db.query(AuditEvent)
        .filter(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    prev_signature = prev_event.signature if prev_event else ""

    # Compute this event's signature
    payload = compute_event_payload(event)
    event.signature = compute_signature(payload, prev_signature)
    event.prev_event_signature = prev_signature
    return event
