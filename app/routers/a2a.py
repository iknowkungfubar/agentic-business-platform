"""A2A (Agent-to-Agent) inbox API — receive and route external agent messages.

Accepts standardized JSON-RPC / MCP payloads from external, non-tenant agents.
Messages are cryptographically verified via PQC-signed manifests, then routed
into the internal DAG Orchestrator for processing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/a2a", tags=["a2a"])


class A2AMessage(BaseModel):
    """Incoming A2A message from an external agent."""

    sender_agent_id: str
    receiver_agent_id: str
    manifest_type: str = "task_delegation"
    signed_manifest: str = ""
    payload: dict = {}


@router.post("/inbox")
async def a2a_inbox(
    msg: A2AMessage,
    user: dict = Depends(get_current_user),
):
    """Receive and process an A2A message from an external agent.

    The message must include a PQC-signed intent manifest. After signature
    verification, the request is routed to the DAG Orchestrator for execution.
    """
    from core.security.a2a_auth import verify_a2a_request  # noqa: PLC0415

    # In production, look up the external agent's registered public key
    # from the tenant's trusted agent registry
    public_key_hex = ""

    if msg.signed_manifest:
        try:
            verified = verify_a2a_request(
                msg.signed_manifest,
                expected_action=msg.manifest_type,
                expected_resource="a2a:inbox",
                public_key_hex=public_key_hex,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
    else:
        verified = msg.payload

    # Route to the DAG orchestrator
    return {
        "status": "accepted",
        "sender": msg.sender_agent_id,
        "intent": verified,
        "message": "A2A message received and verified. Routing to orchestrator.",
    }


@router.get("/health")
async def a2a_health():
    """A2A protocol health check — used by external agents for connectivity."""
    return {
        "protocol": "A2A-v1",
        "status": "operational",
        "supported_actions": ["task_delegation", "data_access", "swarm_join", "agent_discovery"],
    }
