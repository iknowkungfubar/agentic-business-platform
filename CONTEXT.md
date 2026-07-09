# TurinTech Agentic Business Platform — Domain Glossary

## Core Entities

**Organization** — A tenant in the platform. Users, agents, documents, conversations,
audit events, and scan results are scoped to an organization. Maps to a company
or department.

**User** — A human operator of the platform. Has a role (admin, operator, auditor, viewer)
and belongs to an organization. Authenticated via OIDC (production) or PBKDF2 (dev).

**Agent** — An AI agent or service registered with the platform. Has a URL, provider,
status, and belongs to an organization. Health-checkable via reachability probes.

**Document** — An ingested file (text, markdown, PDF, code, etc.). Goes through the
pipeline: ingest → chunk → embed → index.

**Conversation** — A multi-turn chat session between a user and the platform.
Contains messages. Scoped to an organization. Updated on every new message.

**Message** — A single turn in a conversation (user or assistant). Has content,
model tier, and token count. Created via SSE streaming (real-time) or REST (batch).

**AuditEvent** — A recorded security-relevant action with WORM cryptographic chaining.
Each event's signature is a SHA-256 hash of its payload + the previous event's
signature, forming a tamper-evident chain. Append-only.

**APIKey** — A long-lived authentication token for programmatic access. Stored as
SHA-256 hash with a key prefix for identification.

**MCPScanResult** — A persisted MCP security scan result. Stores scan findings,
vulnerability counts, and metadata. Scoped to an organization.

## Architectural Decisions

- **API-first with CLI sibling**: The platform exposes a REST API (FastAPI) as the
  primary integration seam. The CLI calls through the same `app.service` module
  so both entry points share the same behaviour. See `app/service.py`.
- **Route modules**: API routes live in `app/routers/` with one module per domain
  (auth, chat, agents, audit, compliance, costs, eval, health, mcp, policies,
  sbom, dashboard, admin, ingest). See `app/routers/`.
- **Database split**: ORM models live in `app/models/`, engine/session management
  in `app/database.py`. The legacy `app/db.py` was removed in arch v3.
- **Lazy engine**: The SQLAlchemy engine is created lazily and can be reset via
  `reset_engine()` for test isolation. Supports SQLite (dev) and PostgreSQL (prod).
- **SSE streaming**: Chat responses stream tokens in real-time via Server-Sent Events
  (`/chat/stream`). Messages are saved asynchronously via BackgroundTasks.
- **OIDC/SSO auth**: Production deployments use external Identity Providers
  (Keycloak, ZITADEL) with JWKS validation. Falls back to local PBKDF2.
- **WORM audit log**: `AuditEvent` records use SHA-256 cryptographic chaining.
  `create_audit_event()` auto-computes signatures and chain links.
- **Frontend**: React 19 + TypeScript + Vite. Zustand for state, React Router v7
  for routing, Radix UI + Tailwind for components. See `web/src/`.

## Integration Gaps (Known)

- **ACP is vendored but not wired**: The `acp/` submodule contains the Agent Control
  Plane project. Full integration (agent discovery via network scan, compliance
  engine, cost tracking from ACP) is deferred to post-MVP.
- **No identity provider bundling**: OIDC is supported but no IdP (Keycloak/ZITADEL)
  is shipped as part of the Helm chart. Requires external setup.
- **Real inference**: SSE streaming assumes a running LM Studio or OpenAI-compatible
  endpoint. The platform includes graceful degradation with demo mode.

## Model Tiers

| Tier | Task Types | Model Size | Typical Latency |
|------|-----------|------------|-----------------|
| T1 | Search, summarization, simple Q&A | 9B GGUF | < 2s |
| T2 | Data extraction, classification, routing | 9B-14B | < 5s |
| T3 | Code generation, analysis, reasoning | 35B+ | < 30s |
| T4 | Complex multi-step agent tasks | 70B+ or cluster | < 120s |

## Deployment Environments

| Environment | Replicas | Resources | DB Size | Ingress |
|-------------|----------|-----------|---------|---------|
| Development | 1 | 250m CPU / 256Mi RAM | SQLite | localhost |
| Staging | 2 | 500m CPU / 512Mi RAM | 20Gi PG | staging.* |
| Production | 3+ | 1 CPU / 1Gi RAM | 100Gi PG | *.solutions |
