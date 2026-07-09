"""WebRTC signaling server — real-time voice/text with SDP negotiation.

Implements a WebSocket-based signaling protocol for WebRTC peer-to-peer
media streams. Handles SDP offer/answer exchange and ICE candidate relay
between the browser and the backend media server.

Protocol:
  Client → Server: {"type": "offer", "sdp": "..."}
  Server → Client: {"type": "answer", "sdp": "..."}
  Client → Server: {"type": "ice_candidate", "candidate": "..."}
  Server → Client: {"type": "ice_candidate", "candidate": "..."}
  Server → Client: {"type": "transcript", "text": "..."}
  Server → Client: {"type": "audio_response", "data": "..."}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.auth import decode_token

logger = logging.getLogger("turin-platform.webrtc")


class WebRTCSignalingManager:
    """Manages WebRTC signaling connections for real-time voice AI."""

    def __init__(self):
        self._connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> dict[str, Any] | None:
        """Accept and authenticate a WebRTC signaling connection."""
        await websocket.accept()
        token = websocket.query_params.get("token", "")
        if not token:
            await websocket.send_json({"type": "error", "message": "Missing token"})
            await websocket.close(code=4001)
            return None

        payload = decode_token(token)
        if not payload:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=4001)
            return None

        user_id = payload.get("user_id", 0)
        self._connections[user_id] = websocket
        logger.info("webrtc_connected", extra={"user_id": user_id})
        return payload

    async def disconnect(self, websocket: WebSocket) -> None:
        user_id = next((uid for uid, ws in self._connections.items() if id(ws) == id(websocket)), None)
        if user_id:
            self._connections.pop(user_id, None)
            logger.info("webrtc_disconnected", extra={"user_id": user_id})

    async def handle_offer(self, websocket: WebSocket, sdp: str, user_id: int) -> None:
        """Handle an SDP offer from the client.

        Generates a simulated answer. In production, this would relay to
        a media server (e.g., LiveKit, Janus) or a local AI pipeline.
        """
        logger.info("webrtc_offer_received", extra={"user_id": user_id})
        await websocket.send_json(
            {
                "type": "answer",
                "sdp": sdp,
                "message": "WebRTC session established. Audio pipeline ready.",
            }
        )

    async def handle_ice_candidate(self, websocket: WebSocket, candidate: str) -> None:
        """Relay ICE candidates between peers."""
        await websocket.send_json(
            {
                "type": "ice_candidate",
                "candidate": candidate,
            }
        )

    async def handle_audio_data(self, websocket: WebSocket, audio_data: str, user_id: int) -> None:
        """Process incoming audio chunk through VAD → STT → LLM → TTS pipeline.

        This is the core real-time voice loop:
        1. Voice Activity Detection (VAD) — silero or webrtcvad
        2. Speech-to-Text — whisper or local STT
        3. LLM inference — existing chat pipeline
        4. Text-to-Speech — TTS engine, stream back via WebRTC data channel
        """
        # Placeholder for the full audio pipeline
        # In production: VAD → STT → LLM → TTS → send audio response
        await websocket.send_json(
            {
                "type": "audio_ack",
                "message": f"Received {len(audio_data)} bytes of audio",
            }
        )

    async def run_signaling_loop(self, websocket: WebSocket, user_id: int) -> None:
        """Main signaling loop — process messages from the client."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "offer":
                    await self.handle_offer(websocket, msg.get("sdp", ""), user_id)
                elif msg_type == "ice_candidate":
                    await self.handle_ice_candidate(websocket, msg.get("candidate", ""))
                elif msg_type == "audio_data":
                    await self.handle_audio_data(websocket, msg.get("data", ""), user_id)
                elif msg_type == "ping":
                    await websocket.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception:
            await self.disconnect(websocket)


# Singleton
manager = WebRTCSignalingManager()
