# TurinTech Agentic Business Platform

**Sovereign AI infrastructure for regulated enterprises.**

A production-ready, secure AI platform that bridges enterprise needs with compliant AI implementation — supporting local inference, self-hosted models, full data sovereignty, and air-gap capability.

## Quick Start

```bash
# Clone
git clone https://github.com/iknowkungfubar/agentic-business-platform.git
cd agentic-business-platform

# Local dev (SQLite)
uv sync
uv run uvicorn app.api:app --reload

# Production stack (PostgreSQL via Docker)
docker compose up
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

## Architecture

```
INTERFACE       — REST API + CLI (route modules in app/routers/)
ORCHESTRATION   — Intent classifier → model router → task dispatcher
DATA PIPELINE   — Ingest → chunk → embed → index (core/pipeline/)
GOVERNANCE      — Policy engine + eval suite + MCP scanner (core/governance/, core/security/)
HARDENING       — SBOM generator (core/hardening/)
```

The platform is structured as two layers:

- **`core/`** — Pure business logic: pipeline, router, governance, security, hardening. No framework dependencies.
- **`app/`** — FastAPI application layer: route modules, auth, database, middleware, CLI.

## Target Markets

- **Defense contractors** — CMMC 2.0 Level 2 compliance (Phase 2: Nov 10, 2026)
- **Government agencies** — Air-gapped, sovereign AI with zero external API calls
- **Regulated enterprises** — EU AI Act (Aug 2026), GDPR, HIPAA
- **Mid-market** — Enterprise-grade AI without the enterprise IT team

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Route modules** (`app/routers/`) | One module per domain — auth, chat, admin, mcp, sbom. Changes to one don't touch others. |
| **Service layer** (`app/service.py`) | Shared seam between CLI and API — both entry points behave identically. |
| **Lazy engine** (`app/database.py`) | Engine created on first use; `reset_engine()` for test isolation without module reloads. |
| **Lifespan lifecycle** | Modern FastAPI pattern with DB retry + Alembic migrations on startup. |
| **ACP integration** | `agent-control-plane` is an installable path dependency; advanced governance features (health monitoring, shadow AI detection, compliance engine) available when needed. |

## Development

```bash
# Install
uv sync

# Run tests (PYTHONPATH workaround for Hermes venv leakage)
PYTHONPATH="" uv run python -m pytest tests/ -q

# Lint + format
uv run ruff check app/ core/ tests/
uv run ruff format app/ core/ tests/
```

## License

MIT — see [LICENSE](LICENSE) for details.
