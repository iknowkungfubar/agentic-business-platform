"""A2A (Agent-to-Agent) authentication — PQC-signed handshake for external swarms.

Defines the cryptographic handshake protocol for inter-enterprise agent
communication. When Company A's agent wants to negotiate with Company B's
agent on this platform, they must exchange PQC-signed intent manifests
before any data is transacted.

Protocol:
1. Sender creates IntentManifest (action, resource, ttl)
2. Sender signs manifest with their PQC private key
3. Receiver validates signature against Sender's registered public key
4. If valid, the agent is authenticated and the request is routed to the DAG orchestrator
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from core.security.pqc import sign_payload, verify_payload


@dataclass
class IntentManifest:
    """A cryptographically signed intent from an external agent."""

    agent_id: str
    action: str  # e.g., "data_access", "task_delegation", "swarm_join"
    resource: str  # e.g., "documents:read", "agents:discover"
    ttl_seconds: int = 60
    nonce: str = field(default_factory=lambda: str(time.time_ns()))
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "resource": self.resource,
            "ttl_seconds": self.ttl_seconds,
            "nonce": self.nonce,
            "payload": self.payload,
        }


def create_signed_manifest(
    intent: IntentManifest,
    private_key_hex: str,
    algorithm: str | None = None,
) -> str:
    """Create a PQC-signed A2A intent manifest.

    Returns JSON string with manifest + signature for transmission.
    """
    manifest_dict = intent.to_dict()
    signature = sign_payload(manifest_dict, private_key_hex, algorithm)
    return json.dumps(
        {
            "manifest": manifest_dict,
            "signature": signature,
            "algorithm": algorithm or "ed25519",
        }
    )


def verify_a2a_request(
    signed_manifest_json: str,
    expected_action: str,
    expected_resource: str,
    public_key_hex: str,
    max_ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Verify an incoming A2A signed manifest.

    Returns the verified payload dict if valid.
    Raises ValueError on verification failure or expired TTL.
    """
    try:
        data = json.loads(signed_manifest_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid signed manifest format") from exc

    manifest = data.get("manifest", {})
    signature = data.get("signature", "")
    algorithm = data.get("algorithm")

    # Verify signature
    if not verify_payload(manifest, signature, public_key_hex, algorithm):
        raise ValueError("A2A signature verification failed — agent not authenticated")

    # Verify action matches
    if manifest.get("action") != expected_action:
        raise ValueError(f"Action mismatch: expected {expected_action}, got {manifest.get('action')}")

    # Verify resource
    if manifest.get("resource") != expected_resource:
        raise ValueError(f"Resource mismatch: expected {expected_resource}, got {manifest.get('resource')}")

    # Check TTL
    created_at = float(manifest.get("nonce", "0")) / 1e9
    elapsed = time.time() - created_at
    ttl = manifest.get("ttl_seconds", 60)
    if elapsed > ttl:
        raise ValueError(f"Manifest expired (ttl={ttl}s, elapsed={elapsed:.0f}s)")
    if elapsed > max_ttl_seconds:
        raise ValueError(f"Manifest exceeds max TTL of {max_ttl_seconds}s")

    return manifest


def register_external_agent_public_key(
    agent_id: str,
    public_key_hex: str,
    algorithm: str = "ed25519",
) -> dict[str, Any]:
    """Register an external agent's public key for A2A communication.

    In production, this stores the key in a tenant-scoped table.
    Returns a dict with the registration status.
    """
    return {
        "agent_id": agent_id,
        "public_key_hex": public_key_hex[:16] + "...",
        "algorithm": algorithm,
        "registered_at": time.time(),
        "status": "active",
    }
