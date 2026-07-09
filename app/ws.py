"""WebSocket connection manager — real-time event push to browser clients.

Authenticates users via JWT on connection, maps sessions to organizations,
and broadcasts enterprise events from Redis Streams to all connected clients.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.auth import decode_token


class ConnectionManager:
    """Manages WebSocket connections organized by organization_id.

    Each connection is authenticated via JWT on upgrade. Messages are
    broadcast to all connections within an organization, enabling
    real-time updates without polling.
    """

    def __init__(self):
        # {org_id: {websocket: user_info}}
        self._connections: dict[int, dict[int, dict[str, Any]]] = {}
        # {websocket_id: (org_id, websocket)}
        self._sockets: dict[int, tuple[int, WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> dict[str, Any] | None:
        """Accept a WebSocket connection and authenticate via JWT token.

        Expects the token as a query parameter: ws://host/ws?token=xxx
        """
        await websocket.accept()

        # Extract JWT from query params
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
        user_id = payload.get("user_id") or 0

        # Register connection
        if org_id not in self._connections:
            self._connections[org_id] = {}
        self._connections[org_id][id(websocket)] = payload
        self._sockets[id(websocket)] = (org_id, websocket)

        await websocket.send_json({"type": "connected", "org_id": org_id, "user_id": user_id})
        return payload

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        ws_id = id(websocket)
        if ws_id in self._sockets:
            org_id, _ = self._sockets.pop(ws_id)
            if org_id in self._connections:
                self._connections[org_id].pop(ws_id, None)
                if not self._connections[org_id]:
                    del self._connections[org_id]

    async def broadcast_to_org(self, org_id: int, event: dict[str, Any]) -> int:
        """Broadcast an event to all connections in an organization.

        Returns the number of clients the event was sent to.
        """
        sent = 0
        connections = self._connections.get(org_id, {})
        stale = []

        for ws_id, user_info in connections.items():
            _, ws = self._sockets.get(ws_id, (None, None))
            if ws is None:
                stale.append(ws_id)
                continue
            try:
                await ws.send_json(event)
                sent += 1
            except Exception:
                stale.append(ws_id)

        for ws_id in stale:
            await self.disconnect(self._sockets.get(ws_id, (None, None))[1])

        return sent

    async def broadcast_to_all(self, event: dict[str, Any]) -> int:
        """Broadcast an event to all connected clients."""
        total = 0
        for org_id in list(self._connections.keys()):
            total += await self.broadcast_to_org(org_id, event)
        return total

    @property
    def active_connections(self) -> int:
        return len(self._sockets)


# Singleton
manager = ConnectionManager()
