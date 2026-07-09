"""Distributed WebSocket connection manager — Redis Pub/Sub backplane.

Multi-pod Kubernetes support: connections are registered per pod in memory,
but a Redis Pub/Sub channel per organization ensures events reach the user
regardless of which physical pod they're connected to.

Architecture:
  Pod A: User1 (org=5) → WS connected → subscribes Redis channel "org:5:events"
  Pod B: User2 (org=5) → WS connected → subscribes Redis channel "org:5:events"
  Worker publishes to "org:5:events" → Redis fan-out → both pods receive → both clients get the event
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import WebSocket

from app.auth import decode_token


class DistributedConnectionManager:
    """Redis-backed WebSocket manager for horizontally scaled deployments.

    Each pod maintains its own in-memory connection map. A Redis Pub/Sub
    channel per org handles cross-pod broadcasting.
    """

    def __init__(self):
        self._connections: dict[int, dict[int, WebSocket]] = {}  # org_id → {ws_id: ws}
        self._pubsubs: dict[int, Any] = {}  # org_id → Redis pubsub listener

    def _get_redis(self):
        from redis.asyncio import Redis  # noqa: PLC0415

        return Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            socket_connect_timeout=2,
            decode_responses=True,
        )

    async def connect(self, websocket: WebSocket) -> dict[str, Any] | None:
        """Accept and authenticate a WebSocket connection, subscribe to org channel."""
        await websocket.accept()
        token = websocket.query_params.get("token", "")
        if not token:
            await websocket.send_json({"error": "Missing authentication token"})
            await websocket.close(code=4001)
            return None

        payload = decode_token(token)
        if not payload:
            await websocket.send_json({"error": "Invalid or expired token"})
            await websocket.close(code=4001)
            return None

        org_id = payload.get("org_id") or 0
        ws_id = id(websocket)

        if org_id not in self._connections:
            self._connections[org_id] = {}
            # Subscribe to Redis Pub/Sub for this org
            await self._subscribe_org(org_id)

        self._connections[org_id][ws_id] = websocket
        await websocket.send_json({"type": "connected", "org_id": org_id})
        return payload

    async def _subscribe_org(self, org_id: int) -> None:
        """Subscribe to the Redis Pub/Sub channel for this org."""
        try:
            r = self._get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe(f"org:{org_id}:events")
            self._pubsubs[org_id] = (r, pubsub)
            # Start background listener
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self._listen_org(org_id, pubsub))
        except Exception:
            pass

    async def _listen_org(self, org_id: int, pubsub: Any) -> None:
        """Background task: listen to Redis Pub/Sub and broadcast to local connections."""
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                    await self._broadcast_local(org_id, event)
                except Exception:
                    pass
        except Exception:
            pass

    async def _broadcast_local(self, org_id: int, event: dict) -> None:
        """Broadcast an event to all local connections for an org."""
        connections = self._connections.get(org_id, {})
        stale = []
        for ws_id, ws in connections.items():
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws_id)
        for ws_id in stale:
            del connections[ws_id]

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        ws_id = id(websocket)
        for org_id, connections in self._connections.items():
            if ws_id in connections:
                del connections[ws_id]
                if not connections:
                    # Unsubscribe from Redis channel
                    if org_id in self._pubsubs:
                        r, pubsub = self._pubsubs.pop(org_id)
                        try:
                            await pubsub.unsubscribe(f"org:{org_id}:events")
                            await r.aclose()
                        except Exception:
                            pass
                break

    async def publish_org(self, org_id: int, event: dict) -> None:
        """Publish an event to the Redis Pub/Sub channel for an org.

        This is the primary method for cross-pod event delivery.
        """
        try:
            r = self._get_redis()
            await r.publish(f"org:{org_id}:events", json.dumps(event, default=str))
            await r.aclose()
        except Exception:
            pass

    async def broadcast_to_all(self, event: dict) -> None:
        """Broadcast to all connected orgs."""
        for org_id in list(self._connections.keys()):
            await self.publish_org(org_id, event)


# Singleton
manager = DistributedConnectionManager()
