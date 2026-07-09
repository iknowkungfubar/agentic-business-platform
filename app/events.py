"""Enterprise event bus — Redis Stream-backed event publisher.

Publishes structured JSON events to Redis Streams (XADD), which are
consumed by the ARQ worker and dispatched to matching webhook subscriptions.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

# Redis stream key for enterprise events
EVENT_STREAM = "enterprise_events"

# Event types
EVENT_CHAT_COMPLETED = "chat.completed"
EVENT_DOCUMENT_INGESTED = "document.ingested"
EVENT_DOCUMENT_EMBEDDED = "document.embedded"
EVENT_AUDIT_CREATED = "audit.created"


async def publish_event(event_type: str, payload: dict[str, Any], org_id: int | None = None) -> str | None:
    """Publish an event to the Redis Stream.

    Args:
        event_type: Dot-notation event type (e.g. "chat.completed").
        payload: JSON-serializable event payload.
        org_id: Organization ID for tenant-scoped routing.

    Returns:
        The stream entry ID if successful, None otherwise.
    """
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    try:
        from redis.asyncio import Redis  # noqa: PLC0415

        r = Redis(host=redis_host, port=redis_port, db=0, socket_connect_timeout=2)
        event = {
            "event_type": event_type,
            "org_id": str(org_id) if org_id else "",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": json.dumps(payload, default=str),
        }
        entry_id = await r.xadd(EVENT_STREAM, event, maxlen=10000)
        await r.aclose()
        return entry_id
    except Exception:
        return None
