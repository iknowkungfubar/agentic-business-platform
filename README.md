# TurinTech Agentic Business Platform

**Enterprise sovereign AI infrastructure for regulated industries.**

A production-ready, CMMC 2.0 and EU AI Act-compliant AI platform that bridges enterprise needs with secure, compliant AI implementation — supporting local inference, self-hosted models, full data sovereignty, air-gap capability, and OIDC/SSO identity federation.

[![Tests](https://github.com/iknowkungfubar/agentic-business-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/iknowkungfubar/agentic-business-platform/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
┌─────────────────────────────────────────────────────────────┐
│                    ENTERPRISE BOUNDARY                       │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  React 19 Frontend   │  │  FastAPI Backend              │ │
│  │  ┌────────────────┐  │  │  ┌──────────────────────────┐│ │
│  │  │ AuthScreen     │  │  │  │ app/routers/ (15)        ││ │
│  │  │ ChatArea (SSE) │  │  │  │   auth, chat, agents,    ││ │
│  │  │ Dashboard      │──┼──┼──┤   audit, compliance,     ││ │
│  │  │ Sidebar        │  │  │  │   costs, eval, health,   ││ │
│  │  └────────────────┘  │  │  │   mcp, policies, sbom... ││ │
│  │  Zustand State       │  │  ├──────────────────────────┤│ │
│  │  React Router v7     │  │  │ app/middleware.py         ││ │
│  │  Radix UI + Tailwind │  │  │ app/auth.py (OIDC+PBKDF2)││ │
│  └──────────────────────┘  │  │ app/telemetry.py         ││ │
│                            │  │ app/database.py          ││ │
│  ┌──────────────────────┐  │  │ app/config.py            ││ │
│  │  core/               │  │  ├──────────────────────────┤│ │
│  │  pipeline, router,   │  │  │ app/models/ (10)         ││ │
│  │  governance,         │──┼──┤   User, Agent, Document, ││ │
│  │  security, hardening │  │  │   Message, AuditEvent... ││ │
│  └──────────────────────┘  │  └──────────────────────────┘│
│                            │                              │
│  ┌──────────────────────┐  │  ┌──────────────────────────┐│
│  │  Deployment          │  │  │  Infrastructure           ││
│  │  Docker Compose      │  │  │  Prometheus + Grafana    ││
│  │  Helm Chart (K8s)    │  │  │  PostgreSQL + Backup     ││
│  │  Docker Entrypoint   │  │  │  Alembic Migrations      ││
│  └──────────────────────┘  │  └──────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Route modules** (`app/routers/`) | 15 domain-specific modules — auth, chat, agents, audit, compliance, costs, eval, health, mcp, policies, sbom, dashboard, admin, ingest. Changes to one don't touch others. |
| **Lazy engine** (`app/database.py`) | SQLAlchemy engine created on first use; `reset_engine()` for test isolation. Supports SQLite (dev) and PostgreSQL (prod). |
| **SSE Streaming** (`/chat/stream`) | Real-time token streaming from LM Studio via Server-Sent Events. Background task saves messages to DB without blocking. |
| **OIDC/SSO** (`app/auth.py`) | Dual-mode auth: production uses JWKS-validated OIDC tokens from Keycloak/ZITADEL; development falls back to local PBKDF2 hashing. |
| **WORM Audit** (`app/models/audit_event.py`) | Tamper-evident cryptographic chain — each event's SHA-256 signature incorporates the previous event's signature. |
| **Observability** (`app/telemetry.py`) | Structured JSON logging, Prometheus RED metrics (rate/errors/duration), request ID propagation, `/metrics` endpoint. |
| **Lifespan lifecycle** | FastAPI lifespan with PostgreSQL retry loop (12 attempts, 2.5s backoff) and Alembic migration auto-run. |

### Route Modules (15)

| Module | Paths | Purpose |
|--------|-------|---------|
| `agents` | `/api/v1/agents/*` | Agent CRUD + health checks |
| `audit` | `/api/v1/audit/*` | WORM audit event query + chain verification |
| `auth` | `/api/v1/auth/*` | Login, register, OIDC discovery, API keys |
| `chat` | `/api/v1/*` | Classify, route, evaluate, SSE streaming chat |
| `compliance` | `/api/v1/compliance/*` | CMMC compliance report generation |
| `costs` | `/api/v1/costs` | Real token cost aggregates by tier/agent/day |
| `dashboard` | `/admin/dashboard` | Admin web UI (serves React app) |
| `eval` | `/api/v1/eval/*` | Agent output evaluation suite |
| `health` | `/health`, `/health/ready`, `/health/deep` | Liveness, readiness, deep health probes |
| `mcp` | `/api/v1/scan-mcp`, `/api/v1/mcp/results` | MCP security scanning + results storage |
| `policies` | `/api/v1/policies`, `/api/v1/test-policy` | Policy templates and evaluation |
| `sbom` | `/api/v1/sbom` | SBOM generation |
| `admin` | `/api/v1/admin/*` | User, agent, audit-log management |

---

## Frontend (React 19 + TypeScript + Vite)

```bash
cd web
npm install
npm run dev     # Development server on :5173
npm run build   # Production build to web/dist/
```

**Stack:**
- **React 19** with TypeScript strict mode
- **Zustand** for state management (persisted auth token in localStorage)
- **React Router v7** for routing (`/login`, `/chat`, `/admin/dashboard`, etc.)
- **Radix UI** primitives (Dialog, Tabs, Dropdown, Avatar, Toast, Tooltip)
- **Tailwind CSS v4** for styling
- **Lucide React** icons
- **SSE streaming** for real-time chat token rendering

### Components

| Component | Route | Purpose |
|-----------|-------|---------|
| `AuthScreen` | `/login` | Login/register form with org name |
| `ChatArea` | `/chat`, `/chat/:id` | SSE streaming chat with typewriter effect |
| `Dashboard` | `/admin/dashboard` | Agent stats, policy count, health status |
| `Sidebar` | (layout) | Navigation with logout, collapsible |
| `App` | (root) | Auth guard + layout wrapper |

---

## Security & Compliance

### CMMC 2.0 Level 2 Readiness

| Control | Implementation |
|---------|---------------|
| **AC** — Access Control | RBAC (viewer/operator/auditor/admin), OIDC/SSO, API keys |
| **AU** — Audit & Accountability | WORM audit log with cryptographic SHA-256 chain |
| **IA** — Identification & Authentication | PBKDF2 password hashing, JWT tokens |
| **SC** — System & Communications | Configurable CORS, rate limiting per-tenant |
| **AI-1** — Input Validation | Policy engine evaluates agent actions |
| **AI-2** — MFA + RBAC | Role-based access on all endpoints |
| **AI-3** — Output Monitoring | Structured JSON logs with request IDs |
| **AI-4** — Adversarial Testing | Red-team scheduler with automated eval |

### EU AI Act Readiness

- Risk management via policy engine (Article 9)
- Record-keeping via WORM audit log (Article 12)
- Transparency via OpenAPI docs and model cards (Article 13)
- Human oversight via tiered autonomy (Article 14)

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

Includes: Deployment (3 replicas), HPA, PDB, Service, Ingress (TLS), ConfigMap, Secret, PVC for audit data.

### Monitoring

```bash
docker compose --profile monitoring up -d
```

- **Prometheus** scrapes `/metrics` at `:9090`
- **Grafana** at `:3000` (admin/admin) with pre-configured Prometheus datasource
- Key metrics: `http_requests_total`, `http_request_duration_seconds`

### Backup

```bash
# Backup PostgreSQL
./scripts/backup-db.sh ./backups

# Restore
./scripts/restore-db.sh ./backups/turin-platform-20260709_120000.sql.gz

# Data retention (90-day TTL)
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

# Load testing
pip install locust
locust -f locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2

# Pre-commit
pip install pre-commit && pre-commit install
```

---

## API Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **OIDC Discovery:** `http://localhost:8000/auth/.well-known/openid-configuration`

---

## License

MIT — see [LICENSE](LICENSE) for details.

**Target Markets:** Defense contractors (CMMC 2.0), Government agencies (air-gapped, sovereign AI), Regulated enterprises (EU AI Act, GDPR, HIPAA), Mid-market ($10M-$250M) AI infrastructure.
