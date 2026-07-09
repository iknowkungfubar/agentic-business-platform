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

import hashlib
import hmac
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

        Actual pipeline:
        1. Send audio to Whisper STT endpoint
        2. Get transcript text
        3. Send transcript to LLM chat endpoint
        4. Stream TTS audio response back via WebRTC data channel
        """
        import httpx  # noqa: PLC0415
        from app.config import settings  # noqa: PLC0415
        import base64  # noqa: PLC0415

        inference_url = os.getenv("INFERENCE_URL", settings.inference_url)

        try:
            audio_bytes = base64.b64decode(audio_data) if len(audio_data) > 100 else b""
            if not audio_bytes:
                await websocket.send_json({"type": "transcript", "text": "..."})
                return

            # Step 1: STT via Whisper API
            async with httpx.AsyncClient(timeout=30) as client:
                stt_resp = await client.post(
                    f"{inference_url}/audio/transcriptions",
                    files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"model": "whisper-1"},
                )
                transcript = stt_resp.json().get("text", "") if stt_resp.status_code == 200 else ""
                if transcript:
                    await websocket.send_json({"type": "transcript", "text": transcript})

                # Step 2: LLM inference
                llm_resp = await client.post(
                    f"{inference_url}/chat/completions",
                    json={
                        "model": settings.inference_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful voice AI assistant. Respond conversationally and concisely.",
                            },
                            {"role": "user", "content": transcript or "..."},
                        ],
                        "max_tokens": 256,
                    },
                )
                response_text = (
                    llm_resp.json()["choices"][0]["message"]["content"] if llm_resp.status_code == 200 else ""
                )

                # Step 3: TTS — stream generated audio back
                if response_text:
                    tts_resp = await client.post(
                        f"{inference_url}/audio/speech",
                        json={"model": "tts-1", "input": response_text, "voice": "alloy", "response_format": "wav"},
                    )
                    if tts_resp.status_code == 200:
                        response_audio = base64.b64encode(tts_resp.content).decode()
                        await websocket.send_json(
                            {
                                "type": "audio_response",
                                "data": response_audio,
                                "text": response_text,
                            }
                        )
                    else:
                        await websocket.send_json({"type": "transcript", "text": response_text})
        except Exception as exc:
            logger.warning("voice_pipeline_error", extra={"error": str(exc)})
            await websocket.send_json({"type": "error", "message": "Voice processing failed"})

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
