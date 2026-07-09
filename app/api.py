"""TurinTech Agentic Business Platform — Enterprise API Server.

Production-ready REST API with:
- JWT authentication + API key support
- PostgreSQL persistence (org-scoped multi-tenancy)
- Document ingestion and RAG pipeline
- Intent classification and model routing
- Policy evaluation and compliance reporting
- MCP security scanning
- Conversation management
- Agent inventory and health monitoring
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.auth import (
    create_access_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from app.db import (
    APIKey,
    AgentRecord,
    AuditEvent,
    Conversation,
    Document,
    Message,
    Organization,
    User,
    get_db,
    init_db,
)
from sqlalchemy.orm import Session

# ── App Setup ─────────────────────────────────────────────────────

app = FastAPI(
    title="TurinTech Agentic Business Platform",
    version="0.1.0",
    description="Enterprise sovereign AI infrastructure for regulated industries",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ── Auth Dependencies ─────────────────────────────────────────────


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """Extract and validate the current user from JWT or API key."""
    db = next(get_db())

    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            return payload

    if x_api_key:
        # Look up API key
        key_prefix = x_api_key[:10]
        stored = db.query(APIKey).filter(
            APIKey.key_prefix == key_prefix,
            APIKey.is_active == 1,
        ).first()
        if stored and verify_api_key(x_api_key, stored.key_hash):
            user = db.query(User).filter(User.id == stored.user_id).first()
            if user:
                return {
                    "sub": user.email,
                    "user_id": user.id,
                    "org_id": user.organization_id,
                    "role": user.role,
                }

    raise HTTPException(status_code=401, detail="Not authenticated")


def require_role(role: str):
    """Dependency factory: require a minimum role."""
    def checker(user: dict = Depends(get_current_user)):
        role_hierarchy = {"viewer": 0, "operator": 1, "auditor": 1, "admin": 2}
        if role_hierarchy.get(user.get("role", "viewer"), 0) < role_hierarchy.get(role, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()

# ── Health ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "timestamp": datetime.now(UTC).isoformat()}

# ── Auth Endpoints ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""
    org_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@app.post("/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = None
    if req.org_name:
        org = Organization(name=req.org_name, slug=req.org_name.lower().replace(" ", "-"))
        db.add(org)
        db.flush()

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        organization_id=org.id if org else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=user.organization_id,
    )
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "role": user.role, "org_id": user.organization_id},
    )

@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=user.organization_id,
    )
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "role": user.role, "org_id": user.organization_id},
    )

@app.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

@app.post("/auth/api-key")
async def create_api_key(
    name: str = "",
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    raw, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
        user_id=user["user_id"],
        organization_id=user.get("org_id"),
    )
    db.add(api_key)
    db.commit()
    return {"api_key": raw, "key_prefix": key_prefix, "name": name}

# ── Document Ingestion ──────────────────────────────────────────

class IngestResponse(BaseModel):
    id: int
    source: str
    content_length: int
    file_type: str
    file_name: str

@app.post("/documents/ingest", response_model=IngestResponse)
async def ingest_document(
    path: str,
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    from core.pipeline.ingest import DocumentIngester
    try:
        ingester = DocumentIngester()
        doc = ingester.ingest(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = Document(
        source=doc.source,
        content=doc.content,
        file_type=doc.metadata.get("file_type", ""),
        file_name=doc.metadata.get("file_name", ""),
        file_size=doc.metadata.get("file_size", 0),
        organization_id=user.get("org_id"),
        created_by=user["user_id"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return IngestResponse(
        id=record.id,
        source=record.source,
        content_length=len(doc.content),
        file_type=record.file_type,
        file_name=record.file_name,
    )

# ── Classify / Route ────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    text: str

@app.post("/classify")
async def classify(req: ClassifyRequest, user: dict = Depends(get_current_user)):
    from core.router.intent import IntentClassifier
    classifier = IntentClassifier()
    result = classifier.classify(req.text)
    return {"intent": result.intent_type, "confidence": result.confidence, "reason": result.reason}

class RouteRequest(BaseModel):
    text: str

@app.post("/route")
async def route(req: RouteRequest, user: dict = Depends(get_current_user)):
    from core.router.intent import IntentClassifier
    from core.router.selector import ModelSelector
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

# ── Policy Evaluation ───────────────────────────────────────────

class EvaluateRequest(BaseModel):
    action: dict

@app.post("/evaluate")
async def evaluate(req: EvaluateRequest, user: dict = Depends(get_current_user)):
    from core.governance.policy import PolicyEngine
    from core.governance.templates import PolicyTemplates
    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())
    result = engine.evaluate(req.action)
    return {
        "effect": result.effect.value,
        "matched_rule": result.matched_rule,
        "matched_rules": result.matched_rules,
        "details": result.details,
    }

# ── Conversations ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None

@app.post("/chat")
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.router.intent import IntentClassifier
    from core.router.selector import ModelSelector

    # Get or create conversation
    if req.conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == req.conversation_id,
            Conversation.organization_id == user.get("org_id"),
        ).first()
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
    inference_url = os.getenv("INFERENCE_URL", "http://localhost:1234/v1")
    try:
        import httpx
        resp = httpx.post(
            f"{inference_url}/chat/completions",
            json={
                "model": "qwen3.5-9b-deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": f"You are a helpful AI assistant. Intent: {intent.intent_type}. Route: {route.model_tier}."},
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
            tokens_used = 0
    except Exception as e:
        inference_result = f"[Demo mode — inference unavailable: {e}]"
        tokens_used = 0

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

@app.get("/conversations")
async def list_conversations(
    limit: int = 20,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = db.query(Conversation).filter(
        Conversation.organization_id == user.get("org_id"),
    ).order_by(Conversation.updated_at.desc()).limit(limit).all()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()}
        for c in convs
    ]

@app.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.organization_id == user.get("org_id"),
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
    return [
        {"id": m.id, "role": m.role, "content": m.content[:500], "model_tier": m.model_tier, "created_at": m.created_at.isoformat()}
        for m in msgs
    ]

# ── MCP Scanner ─────────────────────────────────────────────────

class ScanMCPRequest(BaseModel):
    url: str
    timeout: float = 5.0

@app.post("/scan-mcp")
async def scan_mcp(req: ScanMCPRequest, user: dict = Depends(require_role("operator"))):
    from core.security.mcp_scanner import MCPScanner
    scanner = MCPScanner(timeout=req.timeout)
    try:
        result = scanner.scan(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "url": result.url,
        "reachable": result.reachable,
        "status_code": result.status_code,
        "is_https": result.is_https,
        "requires_auth": result.requires_auth,
        "findings": [
            {"severity": f.severity.value, "description": f.description, "recommendation": f.recommendation}
            for f in result.findings
        ],
    }

# ── SBOM ─────────────────────────────────────────────────────────

@app.post("/sbom")
async def generate_sbom(project_root: str = ".", user: dict = Depends(require_role("operator"))):
    from core.hardening.sbom import SBOMGenerator
    generator = SBOMGenerator()
    result = generator.generate(project_root=project_root)
    return {
        "project_name": result.project_name,
        "project_version": result.project_version,
        "dependencies": [{"name": d.name, "version": d.version} for d in result.dependencies],
        "vulnerabilities": [
            {"cve": v.cve_id, "severity": v.severity, "package": v.package}
            for v in result.vulnerabilities
        ],
    }

# ── Admin: Users & Agents ────────────────────────────────────────

@app.get("/admin/users")
async def list_users(
    user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = db.query(User).filter(
        User.organization_id == user.get("org_id"),
    ).all()
    return [{"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name} for u in users]

@app.get("/admin/agents")
async def list_agents(
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    agents = db.query(AgentRecord).filter(
        AgentRecord.organization_id == user.get("org_id"),
    ).all()
    return [{"id": a.id, "name": a.name, "url": a.url, "provider": a.provider, "status": a.status} for a in agents]

@app.get("/admin/audit-log")
async def audit_log(
    limit: int = 50,
    user: dict = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    events = db.query(AuditEvent).filter(
        AuditEvent.organization_id == user.get("org_id"),
    ).order_by(AuditEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "agent_id": e.agent_id,
            "action_type": e.action_type,
            "policy_decision": e.policy_decision,
        }
        for e in events
    ]
