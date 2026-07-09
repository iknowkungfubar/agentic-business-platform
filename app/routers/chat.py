"""Classifier, router, evaluate, and chat endpoints with SSE streaming."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Conversation, Message
from app.routers import get_current_user

router = APIRouter(tags=["orchestration"])

# ── Classify ──────────────────────────────────────────────────


class ClassifyRequest(BaseModel):
    text: str


@router.post("/classify")
async def classify(req: ClassifyRequest, user: dict = Depends(get_current_user)):
    from core.router.intent import IntentClassifier  # noqa: PLC0415

    classifier = IntentClassifier()
    result = classifier.classify(req.text)
    return {"intent": result.intent_type, "confidence": result.confidence, "reason": result.reason}


# ── Route ─────────────────────────────────────────────────────


class RouteRequest(BaseModel):
    text: str


@router.post("/route")
async def route(req: RouteRequest, user: dict = Depends(get_current_user)):
    from core.router.intent import IntentClassifier  # noqa: PLC0415
    from core.router.selector import ModelSelector  # noqa: PLC0415

    classifier = IntentClassifier()
    selector = ModelSelector()
    intent = classifier.classify(req.text)
    route_result = selector.select(intent, req.text)
    return {
        "intent": intent.intent_type,
        "intent_confidence": intent.confidence,
        "model_tier": route_result.model_tier,
        "route_confidence": route_result.confidence,
        "estimated_tokens": route_result.estimated_tokens,
        "reason": route_result.reason,
    }


# ── Evaluate (Policy) ─────────────────────────────────────────


class EvaluateRequest(BaseModel):
    action: dict


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest, user: dict = Depends(get_current_user)):
    from core.governance.policy import PolicyEngine  # noqa: PLC0415
    from core.governance.templates import PolicyTemplates  # noqa: PLC0415

    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())
    result = engine.evaluate(req.action)
    return {
        "effect": result.effect.value,
        "matched_rule": result.matched_rule,
        "matched_rules": result.matched_rules,
        "details": result.details,
    }


# ── Chat (SSE Streaming) ─────────────────────────────────────


async def _stream_inference(
    message: str,
    conversation_id: int,
    user: dict[str, Any],
    db: Session,
    background_tasks: BackgroundTasks,
):
    """Generator that streams tokens from LM Studio via SSE and saves to DB on completion."""
    from core.router.intent import IntentClassifier  # noqa: PLC0415
    from core.router.selector import ModelSelector  # noqa: PLC0415

    classifier = IntentClassifier()
    selector = ModelSelector()
    intent = classifier.classify(message)
    route = selector.select(intent, message)

    full_content = ""
    tokens_used = 0
    stream_error: str | None = None

    import httpx  # noqa: PLC0415

    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{inference_url}/chat/completions",
                json={
                    "model": settings.inference_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"You are a helpful AI assistant. Intent: {intent.intent_type}. Route: {route.model_tier}. "
                            'Use <<render_component{"type":"...","props":{...}}>> for UI.',
                        },
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.7,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield f"data: {json.dumps({'error': f'Inference server returned {resp.status_code}: {error_body.decode()}'})}\n\n".encode()
                    stream_error = f"HTTP {resp.status_code}"
                else:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(payload)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")

                            # Check for render_component tool calls in the content
                            if content and "<<render_component" in content:
                                # Extract the JSON args between markers
                                import re as _re

                                match = _re.search(r"<<render_component\s*({.*?})>>", content, _re.DOTALL)
                                if match:
                                    try:
                                        comp_data = json.loads(match.group(1))
                                        yield f"data: {json.dumps({'type': 'ui_component', 'component': comp_data})}\n\n".encode()
                                    except json.JSONDecodeError:
                                        pass
                                    content = _re.sub(r"<<render_component\s*{.*?}>>", "", content)

                            if content:
                                full_content += content
                                yield f"data: {json.dumps({'token': content})}\n\n".encode()
                            # Track token usage from stream
                            usage = chunk.get("usage", {})
                            if usage:
                                tokens_used = usage.get("completion_tokens", 0) or usage.get("total_tokens", 0)
                        except json.JSONDecodeError:
                            continue
    except Exception as exc:
        error_msg = str(exc)
        yield f"data: {json.dumps({'error': f'Inference unavailable: {error_msg}'})}\n\n".encode()
        stream_error = error_msg

    # Save the completed message via background task
    background_tasks.add_task(
        _save_message,
        conversation_id=conversation_id,
        role="assistant",
        content=full_content or f"[Demo mode — inference unavailable: {stream_error}]",
        model_tier=route.model_tier,
        tokens_used=tokens_used,
    )

    # Send completion event with conversation_id
    yield f"data: {json.dumps({'conversation_id': conversation_id, 'done': True})}\n\n".encode()


async def _save_message(
    conversation_id: int,
    role: str,
    content: str,
    model_tier: str,
    tokens_used: int,
) -> None:
    """Background task: save a message record to the database."""
    db = next(get_db())
    try:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_tier=model_tier,
            tokens_used=tokens_used,
        )
        db.add(msg)
        # Update conversation timestamp
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            from datetime import UTC, datetime

            conv.updated_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


@router.post("/chat")
async def chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Non-streaming chat endpoint (backward compatible)."""
    from core.router.intent import IntentClassifier  # noqa: PLC0415
    from core.router.selector import ModelSelector  # noqa: PLC0415

    # Get or create conversation
    if req.conversation_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == req.conversation_id,
                Conversation.organization_id == user.get("org_id"),
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            title=req.message[:80],
            user_id=user["user_id"],
            organization_id=user.get("org_id"),
        )
        db.add(conv)
        db.flush()

    classifier = IntentClassifier()
    selector = ModelSelector()
    intent = classifier.classify(req.message)
    route = selector.select(intent, req.message)

    # Store user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=req.message,
        model_tier=route.model_tier,
    )
    db.add(user_msg)

    # Call LM Studio inference
    inference_result = ""
    tokens_used = 0
    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)

    try:
        import httpx  # noqa: PLC0415

        resp = httpx.post(
            f"{inference_url}/chat/completions",
            json={
                "model": settings.inference_model,
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a helpful AI assistant. Intent: {intent.intent_type}. Route: {route.model_tier}. "
                        'Use <<render_component{"type":"...","props":{...}}>> for UI.',
                    },
                    {"role": "user", "content": req.message},
                ],
                "max_tokens": 1024,
                "temperature": 0.7,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            inference_result = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
        else:
            inference_result = f"[Inference server returned {resp.status_code}]"
    except Exception as exc:
        inference_result = f"[Demo mode — inference unavailable: {exc}]"

    # Save assistant message via background task
    background_tasks.add_task(
        _save_message,
        conversation_id=conv.id,
        role="assistant",
        content=inference_result,
        model_tier=route.model_tier,
        tokens_used=tokens_used,
    )

    return {
        "conversation_id": conv.id,
        "response": inference_result,
        "intent": intent.intent_type,
        "model_tier": route.model_tier,
        "tokens_used": tokens_used,
    }


@router.get("/chat/stream")
async def chat_stream(
    message: str = Query(..., description="User message"),
    conversation_id: int | None = Query(None, description="Existing conversation ID"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streaming chat endpoint using Server-Sent Events."""
    # Get or create conversation
    if conversation_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.organization_id == user.get("org_id"),
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            title=message[:80],
            user_id=user["user_id"],
            organization_id=user.get("org_id"),
        )
        db.add(conv)
        db.flush()

    # Store user message immediately
    from core.router.intent import IntentClassifier  # noqa: PLC0415
    from core.router.selector import ModelSelector  # noqa: PLC0415

    classifier = IntentClassifier()
    selector = ModelSelector()
    intent = classifier.classify(message)
    route = selector.select(intent, message)

    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=message,
        model_tier=route.model_tier,
    )
    db.add(user_msg)
    db.commit()

    return StreamingResponse(
        _stream_inference(message, conv.id, user, db, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Conversations ─────────────────────────────────────────────


@router.get("/conversations")
async def list_conversations(
    limit: int = 20,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.organization_id == user.get("org_id"))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in convs]


@router.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conv_id,
            Conversation.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content[:500],
            "model_tier": m.model_tier,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]
