# ADR-0001: CQRS Database Architecture
**Date:** 2026-07-09  
**Status:** Accepted  
**Deciders:** Principal Architect

## Context
The platform needed to handle thousands of concurrent FastAPI connections without starving the database. Hybrid RAG searches (pgvector + tsvector) are read-heavy and compete with write operations for connection pool slots.

## Decision
Implement CQRS with separate read/write connection pools:
- `DATABASE_URL_PRIMARY` for mutations (INSERT/UPDATE/DELETE)
- `DATABASE_URL_REPLICA` for reads (SELECT, hybrid search)
- PgBouncer in transaction pooling mode in front of PostgreSQL
- `get_db()` → write session, `get_db_read()` → read session
- Falls back to single engine when replica URL is unset

## Consequences
- **Positive**: Read-heavy searches don't block writes. Horizontal scaling of replicas is transparent.
- **Positive**: Lazy engine pattern means zero-config setup for SQLite dev.
- **Negative**: Developers must choose the right session (read vs write) — wrong choice causes errors.
- **Mitigation**: `get_db()` defaults to write session for safety. `get_db_read()` is explicit.

---

# ADR-0002: WORM Audit with SHA-256 Chaining
**Date:** 2026-07-09  
**Status:** Accepted

## Context
CMMC 2.0 Level 2 and EU AI Act require tamper-evident audit logging. Standard database logging (mutable rows, no chain) is insufficient for compliance.

## Decision
Implement cryptographic WORM chaining:
- Each `AuditEvent` stores `signature` (SHA-256 of payload + previous signature) and `prev_event_signature`
- `create_audit_event()` auto-computes the chain at insert time
- Chain is per-organization (cross-tenant chain breaks are impossible)
- Append-only at application level; no cascade deletes

## Consequences
- **Positive**: Tampering with any event breaks the chain for all subsequent events — detectable via `/audit/integrity`
- **Positive**: No external HSM or blockchain dependency
- **Negative**: Cannot modify or delete audit events (by design)
- **Negative**: Chain verification requires scanning all events (O(n))

---

# ADR-0003: Post-Quantum Readiness with Ed25519
**Date:** 2026-07-09  
**Status:** Accepted  
**Deciders:** Lead Cryptographer

## Context
NIST has finalized ML-DSA (FIPS 204), but production-quality Python bindings with hardware support are not yet available. DoD/Federal audits require a "quantum-ready" posture.

## Decision
Use EdDSA (Ed25519) as the active signing algorithm with a pluggable engine architecture:
- `SigningEngine` protocol abstract class
- `Ed25519Engine` (active) — strongest practical option in 2026
- `RSA4096Engine` (fallback) — for interoperability
- `PQC_ALGORITHM` env var controls algorithm selection
- `PQC_REQUIRED` env var fails closed if selected algorithm is unavailable

## Consequences
- **Positive**: Architecture supports seamless ML-DSA migration when libraries reach GA
- **Positive**: Ed25519 provides ~128-bit security with fast verification
- **Negative**: Not truly post-quantum resistant today — labeled "quantum-ready" not "quantum-resistant"
- **Timeline**: Re-evaluate ML-DSA libraries in Q1 2027

---

# ADR-0004: ARQ over Celery for Background Workers
**Date:** 2026-07-09  
**Status:** Accepted

## Context
The platform needs background task processing for document ingestion, webhook dispatch, billing aggregation, and EU AI Act monitoring.

## Decision
Use ARQ (Redis-backed async task queue) over Celery:
- Native async support (coroutines, not threads)
- Simpler deployment (no separate broker, just Redis)
- Built-in cron scheduling via `cron` decorator
- Job timeout, retry, and result storage via Redis

## Consequences
- **Positive**: Zero additional infrastructure beyond existing Redis
- **Positive**: Async-native — no thread pool contention with FastAPI workers
- **Negative**: Less ecosystem than Celery (no built-in monitoring UI)
- **Mitigation**: Prometheus metrics for queue depth and job duration

---

# ADR-0005: Route Module Pattern
**Date:** 2026-07-09  
**Status:** Accepted

## Context
The API surface grew rapidly across 47 phases. A monolithic router file became unmaintainable.

## Decision
One route module per domain in `app/routers/`:
- Each module has its own `APIRouter`, models, and dependencies
- `app/api.py` is the factory — imports all routers, applies middleware, registers lifespan
- Prefixes are applied at include time, not in the router itself
- 26 route modules as of v12.0

## Consequences
- **Positive**: Changes to one domain never touch another
- **Positive**: New feature = new file, no merge conflicts
- **Negative**: Cross-cutting concerns (auth, pagination) must be shared via `app/routers/__init__.py`
- **Negative**: Route discovery requires scanning 26 files
