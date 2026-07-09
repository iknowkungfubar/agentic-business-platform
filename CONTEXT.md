# TurinTech Agentic Business Platform — Domain Glossary

## Core Entities

**Organization** — A tenant in the platform. Users, agents, documents, and conversations
are scoped to an organization. Maps to a company or department.

**User** — A human operator of the platform. Has a role (admin, operator, auditor, viewer)
and belongs to an organization.

**Agent** — An AI agent or service registered with the platform. Has a URL, provider,
status, and belongs to an organization.

**Document** — An ingested file (text, markdown, PDF, code, etc.). Goes through the
pipeline: ingest → chunk → embed → index.

**Conversation** — A multi-turn chat session between a user and the platform.
Contains messages. Scoped to an organization.

**Message** — A single turn in a conversation (user or assistant). Has content,
model tier, and token count.

**AuditEvent** — A recorded security-relevant action. Append-only, used for compliance
and forensics.

**APIKey** — A long-lived authentication token for programmatic access.

## Architectural Decisions

- **API-first with CLI sibling**: The platform exposes a REST API (FastAPI) as the
  primary integration seam. The CLI calls through the same `app.service` module
  so both entry points share the same behaviour. See `app/service.py`.
- **Route modules**: API routes live in `app/routers/` with one module per domain
  (auth, chat, admin, mcp, sbom, health). This gives locality — changes to one
  domain don't touch others.
- **Database split**: ORM models live in `app/models/`, engine/session management
  in `app/database.py`. The legacy `app/db.py` remains as a backward-compat shim.
- **Lazy engine**: The SQLAlchemy engine is created lazily and can be reset via
  `reset_engine()` for test isolation. See `app/database.py`.

## Integration Gaps (Known)

- **ACP is vendored but not wired**: The `acp/` directory contains a copy of the
  Agent Control Plane project, but the platform's own routes don't use ACP's
  agent registry, health monitoring, or compliance engine. The platform has its
  own `AgentRecord` model and admin routes. Decision needed: integrate ACP as a
  dependency or align the platform's models with ACP's.
- **No identity provider**: The platform uses built-in JWT auth. For CMMC/EU AI Act
  compliance, SSO (Keycloak/ZITADEL) with MFA is needed (Sprint 1 in SPEC.md).

## Model Tiers

| Tier | Task Types | Model Size | Typical Latency |
|------|-----------|------------|-----------------|
| T1 | Search, summarization, simple Q&A | 9B GGUF | < 2s |
| T2 | Data extraction, classification, routing | 9B-14B | < 5s |
| T3 | Code generation, analysis, reasoning | 35B+ | < 30s |
| T4 | Complex multi-step agent tasks | 70B+ or cluster | < 120s |
