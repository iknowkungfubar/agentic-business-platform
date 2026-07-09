# TurinTech Agentic Business Platform

**Enterprise sovereign AI infrastructure for regulated industries.**

A production-ready, CMMC 2.0 and EU AI Act-compliant AI platform that bridges enterprise needs with secure, compliant AI implementation — supporting local inference, self-hosted models, full data sovereignty, air-gap capability, OIDC/SSO identity federation, DLP/PII redaction, and human-in-the-loop orchestration.

[![Tests](https://github.com/iknowkungfubar/agentic-business-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/iknowkungfubar/agentic-business-platform/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Contact:** Josh — [josh@turintechsolutions.com](mailto:josh@turintechsolutions.com) — [turintechsolutions.com](https://turintechsolutions.com)

---

## Quick Start

```bash
# Clone
git clone https://github.com/iknowkungfubar/agentic-business-platform.git
cd agentic-business-platform

# Backend — local dev (SQLite)
uv sync
uv run uvicorn app.api:app --reload
# API at http://localhost:8000 | Docs at http://localhost:8000/docs

# Frontend — local dev
cd web
npm install
npm run dev
# UI at http://localhost:5173

# Production stack (PostgreSQL via Docker)
docker compose up -d
# API at http://localhost:8000 | Frontend at http://localhost:3000

# With monitoring stack
docker compose --profile monitoring up -d
# Grafana at http://localhost:3000 (admin/admin)
# Prometheus at http://localhost:9090
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ENTERPRISE BOUNDARY                         │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  React 19 Frontend   │  │  FastAPI Backend (23 routers)    │ │
│  │  ┌────────────────┐  │  │  ┌──────────────────────────────┐│ │
│  │  │ AuthScreen     │  │  │  │ Routes: agents, api_keys,    ││ │
│  │  │ ChatArea (SSE) │  │  │  │ audit, auth, billing, chat,  ││ │
│  │  │ Dashboard      │──┼──┼──┤ compliance, costs, dashboard,││ │
│  │  │ Sidebar        │  │  │  │ eval, feedback, health,       ││ │
│  │  └────────────────┘  │  │  │ ingest, mcp, policies,       ││ │
│  │  i18n + WCAG a11y    │  │  │ prompts, sbom, tenant,       ││ │
│  │  Websocket Store     │  │  │ workflows, admin, agents     ││ │
│  │  Tenant Branding     │  │  ├──────────────────────────────┤│ │
│  └──────────────────────┘  │  │ Middleware: Tenant RLS,      ││ │
│                            │  │  TokenBucket Rate Limiter,   ││ │
│  ┌──────────────────────┐  │  │  RequestID, Metrics, CORS   ││ │
│  │  core/               │  │  ├──────────────────────────────┤│ │
│  │  pipeline, router,   │  │  │ app/models/ (20)             ││ │
│  │  governance,         │──┼──┤  User, Organization, AKSK,   ││ │
│  │  security, hardening │  │  │  Agent, Document, Chunk,     ││ │
│  └──────────────────────┘  │  │  Message, AuditEvent,        ││ │
│                            │  │  Conversation, MCPScan,      ││ │
│  ┌──────────────────────┐  │  │  SemanticCache, Workflow,    ││ │
│  │  Deployment          │  │  │  PromptTemplate, Feedback,   ││ │
│  │  Docker Compose      │  │  │  EventSubscription           ││ │
│  │  Helm Chart (K8s)    │──┼──┤                              ││ │
│  │  PgBouncer           │  │  ├──────────────────────────────┤│ │
│  │  Docker Entrypoint   │  │  │ Infrastructure:              ││ │
│  └──────────────────────┘  │  │  Prometheus + Grafana,       ││ │
│                            │  │  Redis (queue + pub/sub),    ││ │
│                            │  │  PostgreSQL + pgvector,      ││ │
│                            │  │  Alembic (23 migrations)     ││ │
└─────────────────────────────┘  └──────────────────────────────┘│
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Route modules** (`app/routers/`) | 23 domain-specific modules. One per domain — changes don't cross boundaries. |
| **CQRS database** | Read/write splitting via `DATABASE_URL_PRIMARY` / `DATABASE_URL_REPLICA`. `get_db_read()` for SELECTs, `get_db_write()` for mutations. |
| **SSE Streaming** (`/chat/stream`) | Real-time token streaming from LLM via Server-Sent Events. Background task saves without blocking. |
| **OIDC/SSO** (`app/auth.py`) | Dual-mode: JWKS-validated OIDC (Keycloak/ZITADEL) with PBKDF2 fallback for dev. |
| **WORM Audit** | Tamper-evident SHA-256 cryptographic chain — each event's signature incorporates the previous event's signature. |
| **RLS Multi-Tenancy** | PostgreSQL Row-Level Security enforced via `app.current_tenant_id()`. Organization-level data isolation by default. |
| **Observability** | Structured JSON logging, Prometheus RED metrics, OpenTelemetry tracing (FastAPI/HTTPX/SQLAlchemy), request ID propagation. |
| **DLP Pipeline** | Zero-trust PII redaction (SSN, credit cards, emails, API keys) before LLM inference. Post-inference unmasking. |
| **AI Guardrails** | Dual-layer firewall: heuristic jailbreak patterns + LLM-based safety evaluation. `ERR_PROMPT_INJECTION` blocking. |
| **Hybrid RAG** | pgvector semantic search + PostgreSQL tsvector keyword search, combined via Reciprocal Rank Fusion (RRF k=60). |
| **Distributed WebSockets** | Redis Pub/Sub backplane for multi-pod Kubernetes deployments. Per-org event channels. |

### Route Modules (23)

| Module | Path | Purpose |
|--------|------|---------|
| `admin` | `/api/v1/admin/*` | User/agent/audit-log management, GDPR forget, legal holds |
| `agents` | `/api/v1/agents/*` | ACP-backed agent CRUD + health checks |
| `api_keys` | `/api/v1/api-keys/*` | Scoped API key generation, listing, revocation |
| `audit` | `/api/v1/audit/*` | WORM audit event query + chain integrity verification |
| `auth` | `/api/v1/auth/*` | Login, register, OIDC discovery, API key auth |
| `billing` | `/api/v1/billing/usage` | FinOps token usage aggregation |
| `chat` | `/api/v1/*` | Classify, route, evaluate, SSE streaming chat |
| `compliance` | `/api/v1/compliance/*` | Evidence-based CMMC compliance reports |
| `costs` | `/api/v1/costs` | Real token cost aggregates by tier/agent/day |
| `dashboard` | `/admin/dashboard` | Admin web UI |
| `eval` | `/api/v1/eval/*` | Agent output evaluation suite |
| `feedback` | `/api/v1/feedback` | RLHF preference signal collection |
| `health` | `/health*` | Liveness, readiness, deep health probes |
| `ingest` | `/api/v1/documents/*` | Async document ingestion (ARQ worker) |
| `mcp` | `/api/v1/scan-mcp`, `/api/v1/mcp/results` | MCP security scanning |
| `policies` | `/api/v1/policies`, `/api/v1/test-policy` | Policy templates + CMMC evaluation |
| `prompts` | `/api/v1/prompts/*` | LLMOps prompt template registry (CRUD) |
| `sbom` | `/api/v1/sbom` | SBOM generation |
| `tenant` | `/api/v1/tenant/resolve` | White-label domain branding resolution |
| `workflows` | `/api/v1/workflows/*` | HITL approval + workflow management |
| `agents` (external) | `/api/v1/agents/*` | (via ACP inventory) |

*Also: `ws` (WebSocket endpoint), `costs`, `billing`, `feedback`.*

---

## Frontend (React 19 + TypeScript + Vite)

```bash
cd web
npm install
npm run dev     # Development server on :5173
npm run build   # Production build to web/dist/
npm run test    # Vitest component tests
```

**Stack:** React 19, Zustand, React Router v7, Radix UI, Tailwind CSS v4, Lucide React, i18next + react-i18next  
**WCAG 2.1 AA:** aria-live regions, aria-labels on all interactive elements, focus management, sufficient color contrast  
**Real-time:** WebSocket connection manager with auto-reconnect and Redis Pub/Sub  
**White-labeling:** Dynamic tenant branding (custom domain, logo, colors) via CSS custom properties  
**Testing:** Vitest + @testing-library/react (3 component tests)

---

## Security & Compliance

### CMMC 2.0 Level 2 Readiness

| Control | Implementation |
|---------|---------------|
| **AC** — Access Control | RBAC (SUPERADMIN/ORG_ADMIN/AUDITOR/USER), OIDC/SSO, scoped API keys |
| **AU** — Audit & Accountability | WORM SHA-256 cryptographic chain, SIEM webhook dispatch |
| **IA** — Identification & Authentication | OIDC JWKS (production), PBKDF2 (dev), API key dual auth |
| **SC** — System & Communications | Token bucket rate limiter, Redis backplane, per-org data isolation |
| **AI-1** — Adversarial Input | DLP PII redaction + AI guardrail firewall (dual-layer) |
| **AI-2** — MFA + RBAC | Role-based access with `RequireRole` dependency on all endpoints |
| **AI-3** — Output Monitoring | Structured JSON logs, OTel tracing, Prometheus RED metrics |
| **AI-4** — Adversarial Testing | Sandboxed tool execution (memory/CPU quotas, network isolation) |

### EU AI Act Readiness

- Risk management via policy engine (Article 9)
- Record-keeping via WORM audit log (Article 12)
- Transparency via OpenAPI docs, model cards, prompt registry (Article 13)
- Human oversight via tiered autonomy + HITL workflow suspension (Article 14)

### GDPR & Legal Hold

- Right to be Forgotten via SHA-256 anonymization (preserves WORM audit FKs)
- Soft deletes with `deleted_at` on all PII-bearing tables
- Legal hold toggle (SUPERADMIN) prevents data destruction during litigation
- 30-day retention cron skips orgs under legal hold

---

## Operations

### Kubernetes Deployment

```bash
# Install via Helm
helm install turin-platform ./deploy/helm/turin-platform \
  -f deploy/helm/turin-platform/values-production.yaml \
  --set database.password=$PGPASSWORD \
  --set jwt.secret=$JWT_SECRET
```

Includes: Deployment (3 replicas), HPA, PDB, Service, Ingress (TLS), ConfigMap, Secret, PVC.

### Database Stack

- PostgreSQL 16 with pgvector extension (384-dim embeddings)
- PgBouncer for transaction pooling (500 concurrent connections)
- CQRS: separate primary and replica connection pools
- Alembic: 23 migrations

### Monitoring

```bash
docker compose --profile monitoring up -d
```

- Prometheus scrapes `/metrics` at `:9090`
- Grafana at `:3000` (admin/admin)
- OpenTelemetry traces (OTLP export, Gen-AI semantic conventions)
- Key metrics: `http_requests_total`, `http_request_duration_seconds`

### Backup & Retention

```bash
# Backup PostgreSQL
./scripts/backup-db.sh ./backups

# Restore
./scripts/restore-db.sh ./backups/turin-platform-latest.sql.gz

# Data retention (90-day TTL, skips legal hold orgs)
./scripts/retention-cleanup.sh
```

---

## Development

```bash
# Backend
uv sync
PYTHONPATH="" uv run python -m pytest tests/ -q
uv run ruff check app/ core/ tests/
uv run ruff format app/ core/ tests/

# Frontend
cd web
npm run lint
npm run build
npm run test

# Load testing
pip install locust
locust -f locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2

# Pre-commit (ruff format + lint, trailing whitespace, secrets scan)
pip install pre-commit && pre-commit install

# ARQ worker (background ingestion, webhooks, metering)
python -m app.worker
```

---

## API Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **OIDC Discovery:** `http://localhost:8000/auth/.well-known/openid-configuration`
- **WebSocket:** `ws://localhost:8000/ws?token=<jwt_token>`

---

## License

MIT — see [LICENSE](LICENSE) for details.

**Contact:** Josh Barker — [josh@turintechsolutions.com](mailto:josh@turintechsolutions.com) — [turintechsolutions.com](https://turintechsolutions.com)

**Target Markets:** Defense contractors (CMMC 2.0), Government agencies (air-gapped, sovereign AI), Regulated enterprises (EU AI Act, GDPR, HIPAA), Mid-market ($10M-$250M) AI infrastructure.
