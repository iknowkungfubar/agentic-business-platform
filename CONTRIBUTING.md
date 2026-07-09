# Contributing to TurinTech Agentic Business Platform

## Development Setup

```bash
# Prerequisites
# - Python 3.12+
# - Node.js 22+
# - Docker & Docker Compose (for PostgreSQL + Redis)
# - uv (Python package manager)

# Backend
cd agentic-business-platform
uv sync
cp env-example.txt .env  # Edit as needed
uv run uvicorn app.api:app --reload

# Frontend
cd web
npm install
npm run dev

# Database (PostgreSQL + Redis via Docker)
docker compose up -d db redis

# Run tests
PYTHONPATH="" uv run python -m pytest tests/ -q
cd web && npx vitest run
```

## Architecture Overview

```
web/               — React 19 + TypeScript frontend (Vite)
app/               — FastAPI backend
  routers/         — 26 route modules (one per domain)
  models/          — 22 SQLAlchemy ORM models
  database.py      — CQRS engine (primary/replica sessions)
  auth.py          — OIDC + PBKDF2 authentication
  middleware.py    — Token bucket rate limiter
  telemetry.py     — Structured logging, Prometheus, OpenTelemetry
  ws.py            — Distributed WebSocket manager (Redis Pub/Sub)
  ws_voice.py      — WebRTC signaling server
  worker.py        — ARQ background worker (5 task types)
core/              — Pure business logic (no framework deps)
  pipeline/        — Ingestion, chunking, embedding, hybrid search
  router/          — Intent classifier, model selector
  governance/      — Policy engine, eval suite, templates
  security/        — DLP, guardrails, PQC signing, A2A auth
deploy/            — Helm chart, Docker, Prometheus, Grafana
migrations/        — Alembic (26 migrations)
```

## Pull Request Workflow

1. Fork the repo and create a feature branch from `main`
2. Write tests first (TDD) — includes backend pytest + frontend vitest
3. Ensure all tests pass: `PYTHONPATH="" uv run python -m pytest tests/ -q`
4. Run ruff linter: `uv run ruff check app/ core/ tests/`
5. Format: `uv run ruff format app/ core/ tests/`
6. Submit PR with a clear description of changes and why

## E2E Testing

Full-stack integration tests require Docker:

```bash
# Start the test stack
docker compose -f docker-compose.test.yml up -d

# Wait for health
./scripts/wait-for-health.sh

# Run E2E tests
PYTHONPATH="" uv run python -m pytest tests/e2e/ -v --timeout=60

# Cleanup
docker compose -f docker-compose.test.yml down
```

## Code Standards

- **Python**: 3.12+, ruff linting, type annotations on all functions
- **TypeScript**: Strict mode, no `any` unless unavoidable, React functional components
- **SQLAlchemy**: Lazy engine pattern, CQRS read/write sessions, all queries scoped to org_id
- **Security**: Every endpoint has explicit `RequireRole` or `get_current_user` dependency
- **Logging**: Structured JSON, not string interpolation — use `extra={}` dicts

## Contact

Josh Barker — josh@turintechsolutions.com — turintechsolutions.com
