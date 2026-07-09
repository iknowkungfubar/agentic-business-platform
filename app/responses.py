"""API response models — typed responses for OpenAPI documentation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Health ───────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    timestamp: str


# ── Auth ─────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Agents ───────────────────────────────────────────────────


class AgentResponse(BaseModel):
    id: int
    name: str
    url: str
    provider: str
    status: str
    tags: str | None = None
    last_seen: str | None = None
    created_at: str | None = None


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Policies ─────────────────────────────────────────────────


class PolicyListResponse(BaseModel):
    frameworks: list[str]
    policies: list[dict]
    total: int


class PolicyTestResponse(BaseModel):
    effect: str
    matched_rule: str | None = None
    matched_rules: list[str] = []
    details: dict[str, Any] = {}


# ── Eval ─────────────────────────────────────────────────────


class EvalRunResponse(BaseModel):
    agent_id: str
    overall_score: float
    threshold: float
    passed: bool
    scores: dict[str, float]
