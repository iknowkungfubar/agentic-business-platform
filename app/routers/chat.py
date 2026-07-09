"""Classifier, router, evaluate, and chat endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import Conversation, Message, get_db
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


# ── Chat ──────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    # Classify and route
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

    # Try to call LM Studio inference
    inference_result = ""
    tokens_used = 0
    inference_url = os.getenv("INFERENCE_URL", "http://localhost:1234/v1")
    try:
        import httpx  # noqa: PLC0415

        resp = httpx.post(
            f"{inference_url}/chat/completions",
            json={
                "model": "qwen3.5-9b-deepseek-v4-flash",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"You are a helpful AI assistant. Intent: {intent.intent_type}. Route: {route.model_tier}."
                        ),
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
    except Exception as e:
        inference_result = f"[Demo mode — inference unavailable: {e}]"

    # Store assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=inference_result,
        model_tier=route.model_tier,
        tokens_used=tokens_used,
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "conversation_id": conv.id,
        "response": inference_result,
        "intent": intent.intent_type,
        "model_tier": route.model_tier,
        "tokens_used": tokens_used,
    }


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
