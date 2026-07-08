# Spec: TurinTech Agentic Business Platform

## Status: v0.1 — Forward Specification
## Date: 2026-07-08
## Previous: N/A (new project)
## Next: Sprint 1 (Compliance Foundation)

---

## Objective

Build a production-ready, sovereign AI platform that bridges enterprise needs with secure, compliant AI implementation. The platform must support local inference and self-hosted models for full data sovereignty, making it suitable for organizations with strict compliance requirements — defense contractors (CMMC 2.0), government agencies, EU-regulated enterprises (EU AI Act, GDPR), and any organization handling Controlled Unclassified Information (CUI).

**Target users:**
- Enterprise IT/Ops teams deploying AI agents at scale
- Defense contractors needing CMMC-compliant AI infrastructure
- Mid-market companies ($10M-$250M) implementing AI without dedicated ops teams
- Government agencies requiring air-gapped or sovereign AI

**Success criteria:**
- All 7 layers functional and integrated end-to-end
- Compliant with CMMC Level 2 (self-certifiable and C3PAO-auditable)
- Compliant with EU AI Act Articles 9-14
- Capable of air-gapped deployment with zero external API calls
- Sub-10 minute deployment for standard configurations

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE BOUNDARY                           │
│  (Air-gap capable — controlled internet with guardrails)        │
│                                                                  │
│  L1 ┌──────────────────────────────────────────────────────┐    │
│     │  INTERFACE LAYER                                      │    │
│     │  Agentic Chat (staff)  │  Admin Panel (engineering)   │    │
│     │  API Gateway (MCP + REST + WebSocket)                 │    │
│     └──────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  L2 ┌──────────────────────────▼───────────────────────────┐    │
│     │  ORCHESTRATION LAYER                                  │    │
│     │  Intent Classifier → Model Selector → Task Router     │    │
│     │  → Agent Executor → Verifier Loop                     │    │
│     │  Small model (9B) → simple tasks                      │    │
│     │  Large model (35B+ cluster) → complex reasoning        │    │
│     └──────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  L3 ┌──────────────────────────▼───────────────────────────┐    │
│     │  KNOWLEDGE & MEMORY LAYER                             │    │
│     │  Vector DB (RAG) │ Graph Memory │ Semantic Cache     │    │
│     │  Session Memory │ Role-Based Access at chunk level    │    │
│     └──────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  L4 ┌──────────────────────────▼───────────────────────────┐    │
│     │  DATA PIPELINE LAYER                                  │    │
│     │  Ingest → Clean → Chunk → Embed → Index → RBAC       │    │
│     │  → Audit Trail                                        │    │
│     │  Inputs: PDF, email, Slack, Teams, SharePoint, wikis  │    │
│     └──────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  L5 ┌──────────────────────────▼───────────────────────────┐    │
│     │  GOVERNANCE & MONITORING LAYER                        │    │
│     │  ACP + Policy-as-Code (OPA) + Agent Eval Engine       │    │
│     │  + MCP Security Scanner + Shadow AI Detection         │    │
│     │  + Cost Tracking + SBOM Generation                    │    │
│     └──────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  L6 ┌──────────────────────────▼───────────────────────────┐    │
│     │  SECURITY & COMPLIANCE LAYER                          │    │
│     │  PKI / mTLS │ RBAC (Keycloak/ZITADEL)                 │    │
│     │  WORM Audit Logs │ CMMC Evidence │ EU AI Act Docs    │    │
│     │  PQC-ready (ML-KEM FIPS 203)                          │    │
│     └──────────────────────────────────────────────────────┘    │
│                                                                  │
│  L7 ┌──────────────────────────────────────────────────────┐    │
│     │  INTERNET CONTROL LAYER (Optional Air-Gap Mode)      │    │
│     │  Controlled egress proxy │ Allowlist │ No egress     │    │
│     │  Offline model delivery │ Signed artifact pipeline   │    │
│     │  Degraded-mode operation                              │    │
│     └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer Descriptions

### Layer 1: Interface

**Components:**
- **Agentic Chat Frontend** — Staff-facing conversational UI with multi-turn chat, file upload, conversation history, agent handoff. Primary interaction point for non-technical users.
- **Admin Panel** — Engineering-facing dashboard for configuration, monitoring, policy management, and audit review.
- **API Gateway** — Unified MCP + REST + WebSocket endpoint for all platform services. Routes requests to the appropriate internal service.

**Key decisions:**
- Chat frontend: React/TypeScript or neur-os chat as foundation
- Admin dashboard: HALF dashboard or ACP dashboard as foundation
- API Gateway: Caddy (from IronSilo refactor) or custom FastAPI gateway

**Integration points:**
- NeurOS chat UI → adapt for enterprise agentic chat
- HALF dashboard → reuse for admin panel
- IronSilo Caddy → serve as API gateway

---

### Layer 2: Orchestration

**Components:**
- **Intent Classifier** — Classifies incoming tasks by type (summarization, data extraction, code generation, reasoning, search, Q&A)
- **Complexity Estimator** — Estimates task complexity based on token count, domain, precision requirements, and required tool access
- **Model Selector** — Routes simple tasks to small local models (9B class: qwen3.5-9b-deepseek-v4-flash, qwopus3.5-9b-coder-mtp) and complex tasks to large reasoning models (35B+ cluster or cloud)
- **Task Router** — Dispatches tasks to appropriate agent executors with isolation
- **Verifier Loop** — Evaluates agent output against criteria before returning to user

**Key decisions:**
- Use HALF orchestrator pattern as foundation
- Model routing: intent-based with automatic fallback chain
- Small model: 9B GGUF via llama.cpp (CPU-friendly for simple tasks)
- Large model: 35B+ via vLLM or llama.cpp (requires GPU cluster)
- Verifier: no-slop-harness evaluation patterns

**Model routing tiers:**

| Tier | Task Types | Model Size | Hardware | Latency Target |
|------|-----------|------------|----------|---------------|
| T1 | Search, summarization, simple Q&A | 9B GGUF | CPU or any GPU | < 2s |
| T2 | Data extraction, classification, routing | 9B-14B | GPU | < 5s |
| T3 | Code generation, analysis, reasoning | 35B+ | GPU cluster | < 30s |
| T4 | Complex multi-step agent tasks | 70B+ or cluster | Multiple GPUs | < 120s |

---

### Layer 3: Knowledge & Memory

**Components:**
- **Vector Database** — Self-hosted vector storage for RAG. LightRAG (from IronSilo) or pgvector.
- **Graph Memory** — Entity-relationship knowledge graph for organizational context, user preferences, cross-session memory.
- **Semantic Cache** — Cache repeated retrieval results to reduce inference cost and latency.
- **Session Memory** — Per-conversation context with TTL and role-based access.
- **Role-Based Access at Chunk Level** — Every document chunk tagged with access permissions; retrieval respects user role.

**Key decisions:**
- Vector DB: LightRAG (already deployed in IronSilo) or Qdrant for scale
- Graph memory: sqlite-vec + entity extraction pipeline
- Chunk-level RBAC: ring-fenced-rag pattern (zero-trust RAG)

---

### Layer 4: Data Pipeline

**Components:**
- **Ingestion** — Document ingestion from multiple sources: PDF, email (IMAP), Slack/Teams exports, SharePoint/OneDrive, wikis/confluence, code repositories, databases
- **Cleaning** — Normalization, deduplication, PII detection and redaction, format conversion to markdown
- **Chunking** — Intelligent chunking with overlap, preserving document structure (headers, lists, tables)
- **Embedding** — Local embedding via nomic-embed-text or BGE-M3 running on CPU/GPU
- **Indexing** — Vector index with metadata filtering, hybrid search (semantic + BM25)
- **RBAC at Chunk Level** — Access control applied at index time so retrieval respects user permissions
- **Audit Trail** — Every document lifecycle event logged

**Key decisions:**
- Build on ring-fenced-rag ingestion patterns
- Local embeddings via LM Studio inference endpoint
- Hybrid retrieval: semantic search + BM25 reranking
- PII redaction: presidio or custom regex-based

---

### Layer 5: Governance & Monitoring

**Components:**
- **Agent Control Plane** — Agent discovery, health monitoring, cost tracking, alerts, shadow AI detection (existing ACP)
- **Policy-as-Code (OPA)** — Open Policy Agent evaluating every agent action (tool call, data access, model selection) against defined Rego policies before execution
- **Agent Evaluation Engine** — Automated eval suite scoring agent outputs against criteria: correctness, safety, compliance, cost efficiency. Red-team scheduling and result tracking.
- **MCP Security Scanner** — Automated audit of MCP server configurations: auth, exposure, dependency vulnerabilities
- **SBOM Generation** — Syft/Trivy pipeline for all platform components
- **Cost Tracking** — Per-agent, per-model, per-department inference and infrastructure costs

**Key decisions:**
- ACP is the foundation — needs policy engine + eval + MCP scanner
- OPA sidecar deployment — each agent action hits OPA before execution
- Eval engine: no-slop-harness patterns adapted for agent output evaluation
- MCP scanner: new build or integrate with existing tools

---

### Layer 6: Security & Compliance

**Components:**
- **Identity Provider** — Keycloak or ZITADEL with SSO (SAML/OIDC), MFA, role mapping (admin/operator/auditor/user)
- **Service-to-Service mTLS** — All internal communication authenticated and encrypted
- **WORM Audit Logs** — Append-only, cryptographically signed, tamper-evident log storage backing to WORM media
- **Compliance Evidence Engine** — Auto-generates compliance reports mapping agent actions to:
  - NIST SP 800-171 (110+ controls)
  - CMMC Level 2 (AI framework overlay)
  - EU AI Act Articles 9-14
  - GDPR Articles 5, 32
- **PQC Readiness** — Hybrid TLS 1.3 with X25519 + ML-KEM (FIPS 203), crypto-agile design

---

### Layer 7: Internet Control (Optional Air-Gap)

**Components:**
- **Controlled Egress Proxy** — Allowlist-based external access with full audit logging
- **Offline Model Delivery** — Signed model bundles delivered via encrypted media, verified checksums
- **Artifact Pipeline** — Update mechanism for air-gapped deployments (signed bundles, staged rollout)
- **Degraded-Mode Operation** — Graceful fallback if external services unavailable; core functionality works offline
- **Network Segmentation** — Physical or logical isolation with one-way data diodes

---

## Tech Stack

| Component | Technology | Reasoning |
|-----------|-----------|-----------|
| **Backend API** | Python FastAPI | Existing across ACP, IronSilo, HALF; team expertise |
| **Frontend** | React/TypeScript + Vite | Existing in HALF; broad ecosystem |
| **API Gateway** | Caddy (from IronSilo refactor) | 56-line config vs 214-line Traefik; 20MB lighter |
| **Identity** | ZITADEL (greenfield) / Keycloak (enterprise) | Both self-hosted, SSO, audit-logging |
| **Vector DB** | LightRAG → Qdrant (scale) | LightRAG already deployed; Qdrant for production |
| **Memory** | sqlite-vec (local) / Neo4j (graph) | sqlite-vec already in IronSilo |
| **Inference** | llama.cpp + LM Studio (local) / vLLM (cluster) | All self-hostable; ROCm/AMD support |
| **Orchestration** | HALF + custom model router | HALF already built; needs routing layer |
| **Policy Engine** | Open Policy Agent (OPA) | Industry standard, sidecar deployment |
| **Monitoring** | Prometheus + Grafana | Already in ACP and IronSilo |
| **Audit Logs** | Append-only SQLite with signing | Lightweight, tamper-evident |
| **MCP Protocol** | MCP 2026-07-28 RC (stateless) | Already in IronSilo Phase 3 |
| **Containers** | Docker / Podman | Both supported; Podman preferred for air-gap |

---

## Existing Repo Integration Map

| Repo | What It Provides | What Needs Building |
|------|-----------------|-------------------|
| **agent-control-plane** | Agent governance foundation (L5): discovery, health, cost, shadow AI, alerts, multi-user | Policy engine integration, eval engine, compliance export, MCP scanner |
| **IronSilo** | Local inference proxy (L2), LightRAG (L3), Caddy gateway (L1), memory (L3) | Only needs structured model routing + air-gap hardening |
| **HALF** | Multi-agent orchestration (L2), worktree isolation, agent mail, dashboard (L1) | Needs model router + intent classifier integration |
| **ring-fenced-rag** | Zero-trust RAG with RBAC (L3, L4) | Needs data pipeline extension (ingest/clean for unstructured) |
| **no-slop-harness** | Quality enforcement patterns (L5) | Adapt for agent output evaluation |
| **NeurOS** | Chat frontend (L1) | Adapt for enterprise agentic chat |

---

## Sprint Plan

### Sprint 1 (Weeks 1-4): Compliance Foundation → NOW
**Build:** Compliance evidence engine + RBAC + WORM audit

Files: `agent-control-plane/src/acp/compliance/`

| Task | Estimate | Dependencies |
|------|----------|-------------|
| T1.1 ZITADEL/Keycloak deployment with SSO | 1 week | None |
| T1.2 Role-based access control across ACP | 1 week | T1.1 |
| T1.3 WORM audit log with cryptographic signing | 1 week | None |
| T1.4 Compliance evidence generator (CMMC + EU AI Act) | 1 week | T1.2, T1.3 |
| T1.5 Compliance report templates | 0.5 week | T1.4 |

### Sprint 2 (Weeks 5-8): Data Pipeline
**Build:** Document ingestion + model router

| Task | Estimate | Dependencies |
|------|----------|-------------|
| T2.1 Document ingestion pipeline (PDF, email, Slack, wiki) | 2 weeks | None |
| T2.2 Cleaning + chunking + embedding pipeline | 1 week | T2.1 |
| T2.3 Multi-model router (intent → complexity → model) | 2 weeks | None |
| T2.4 Small + large inference integration | 1 week | T2.3 |

### Sprint 3 (Weeks 9-12): Governance Core
**Build:** Policy-as-code + agent evaluation

| Task | Estimate | Dependencies |
|------|----------|-------------|
| T3.1 OPA/Rego policy engine deployment | 1 week | T1.2 |
| T3.2 Policy templates (CMMC, GDPR, EU AI Act) | 1 week | T3.1 |
| T3.3 Agent eval suite with scorecards | 2 weeks | None |
| T3.4 Red-team scheduler + results tracking | 1 week | T3.3 |

### Sprint 4 (Weeks 13-16): Security & Edge
**Build:** MCP scanner + air-gap + internet gateway

| Task | Estimate | Dependencies |
|------|----------|-------------|
| T4.1 MCP security scanner (CLI + dashboard) | 2 weeks | None |
| T4.2 Air-gapped deployment blueprint | 1 week | None |
| T4.3 Offline model delivery + update pipeline | 1 week | T4.2 |
| T4.4 Controlled internet gateway + guardrails | 1 week | T4.2 |
| T4.5 Degraded-mode operations | 0.5 week | T4.2 |

### Sprint 5 (Weeks 17-20): Polish & Scale
**Build:** Enterprise chat + SBOM + production hardening

| Task | Estimate | Dependencies |
|------|----------|-------------|
| T5.1 Enterprise agentic chat frontend | 2 weeks | None |
| T5.2 SBOM pipeline (Syft/Trivy integrated) | 1 week | None |
| T5.3 Full degraded-mode and failover | 1 week | T4.5 |
| T5.4 Production hardening + documentation | 1 week | All |

---

## Compliance Mapping

### CMMC 2.0 Level 2 (NIST SP 800-171 + AI Framework)

The FY2026 NDAA Section 1513 adds four AI-specific control categories on top of NIST 800-171:

| CMMC Requirement | Platform Control | Sprint |
|-----------------|-----------------|--------|
| AC — Access Control | ZITADEL/Keycloak RBAC, mTLS service-to-service | S1 |
| AU — Audit & Accountability | WORM audit log, cryptographic signing, SIEM integration | S1 |
| IA — Identification & Authentication | SSO, MFA, short-lived tokens | S1 |
| SC — System & Communications | mTLS, TLS 1.3, PQC-ready | S1 + S4 |
| AI-1 — Input Validation | OPA policy engine, anti-prompt-injection | S3 |
| AI-2 — MFA + RBAC | Identity provider on all endpoints | S1 |
| AI-3 — Output Monitoring | Structured JSON logs, anomaly detection | S1 + S3 |
| AI-4 — Adversarial Testing | Quarterly red-team, automated eval | S3 |

### EU AI Act (Articles 9-14)

| Article | Requirement | Platform Control | Sprint |
|---------|-------------|-----------------|--------|
| Art 9 | Risk management system | OPA policy engine + risk classification | S3 |
| Art 10 | Training data governance | Data pipeline audit trail | S2 |
| Art 11 | Technical documentation | Compliance evidence generator | S1 |
| Art 12 | Record-keeping / logging | WORM audit log | S1 |
| Art 13 | Transparency | Model cards, agent disclosure | S3 |
| Art 14 | Human oversight | HITL gates, tiered autonomy | S3 |

### GDPR

| Article | Requirement | Platform Control | Sprint |
|---------|-------------|-----------------|--------|
| Art 5 | Data minimization | TTL-based retention, auto-purge | S2 |
| Art 17 | Right to erasure | Data deletion API, cascade cleanup | S2 |
| Art 32 | Security of processing | Encryption, access control, audit | S1 |

---

## Data Model (Core Entities)

```
Agent {
  id: UUID
  name: string
  url: string
  provider: string
  tags: string[]
  status: "active" | "inactive" | "degraded"
  owner: User
  created_at: datetime
  updated_at: datetime
}

User {
  id: UUID
  email: string
  role: "admin" | "operator" | "auditor" | "user"
  department: string
  teams: Team[]
  mfa_enabled: boolean
}

AuditEvent {
  id: UUID (monotonic)
  timestamp: datetime
  agent_id: UUID
  user_id: UUID
  action_type: string
  resource_type: string
  resource_id: string
  input_hash: string
  output_hash: string
  policy_decision: "allow" | "deny" | "escalate"
  signature: string  // cryptographic signature of this event
  prev_event_signature: string  // chain hash for WORM integrity
}

Policy {
  id: UUID
  name: string
  rego: string  // OPA Rego policy code
  scope: "agent" | "user" | "data" | "network"
  severity: "block" | "warn" | "log"
  enabled: boolean
  tags: string[]
}

ComplianceReport {
  id: UUID
  framework: "CMMC-2.0" | "EU-AI-ACT" | "GDPR" | "SOC-2"
  generated_at: datetime
  report_period_start: datetime
  report_period_end: datetime
  controls: ComplianceControl[]
  status: "pass" | "fail" | "not-applicable"
}

ComplianceControl {
  id: string  // e.g. "AC.1.001"
  name: string
  status: "passed" | "failed" | "not-tested"
  evidence: Evidence[]
  last_tested: datetime
}

Evidence {
  id: UUID
  audit_event_ids: UUID[]
  description: string
  collected_at: datetime
  expires_at: datetime
}
```

---

## API Contracts

### Core Platform API (REST)

```
GET  /api/v1/agents              → List agents
POST /api/v1/agents              → Register agent
GET  /api/v1/agents/:id          → Agent detail
POST /api/v1/agents/:id/health   → Trigger health check

GET  /api/v1/audit/events        → Query audit events (filterable)
GET  /api/v1/audit/events/:id    → Single audit event with chain verification
GET  /api/v1/audit/integrity     → Verify audit log chain integrity

POST /api/v1/compliance/report   → Generate compliance report
GET  /api/v1/compliance/reports  → List reports
GET  /api/v1/compliance/reports/:id  → Download report (PDF/JSON)
GET  /api/v1/compliance/status   → Current compliance status dashboard

GET  /api/v1/policies            → List policies
POST /api/v1/policies            → Create policy
PUT  /api/v1/policies/:id        → Update policy
POST /api/v1/policies/:id/test   → Test policy against sample action

POST /api/v1/chat               → Send message to agentic chat
GET  /api/v1/chat/conversations  → List conversations
GET  /api/v1/chat/conversations/:id  → Get conversation history

GET  /api/v1/mcp/scan           → Run MCP security scan
GET  /api/v1/mcp/results        → List scan results

GET  /api/v1/eval/tasks         → List eval tasks
POST /api/v1/eval/run           → Run eval suite
GET  /api/v1/eval/results/:id   → Get eval report

GET  /api/v1/costs              → Cost dashboard by agent/model/department
```

### MCP Tools (Agent-Facing)

```
agent.list           → List available agents
agent.health         → Check agent health
policy.evaluate      → Evaluate action against policies
audit.log            → Log audit event (WORM)
compliance.status    → Current compliance posture
data.ingest          → Ingest document into pipeline
data.search          → Search across all indexed data (with RBAC)
chat.send            → Send message to agentic chat
```

---

## Project Structure

```
agentic-business-platform/
├── platform/                    # Core platform backend
│   ├── api/                    # FastAPI application
│   │   ├── routes/            # API route handlers
│   │   ├── models/            # Pydantic models / schemas
│   │   └── middleware/        # Auth, audit, rate limiting
│   ├── compliance/            # Compliance evidence engine  ← SPRINT 1
│   │   ├── engine.py          # Report generation core
│   │   ├── controls/          # Control framework definitions
│   │   │   ├── cmmc.py        # CMMC 2.0 Level 2 controls
│   │   │   ├── eu_ai_act.py   # EU AI Act articles
│   │   │   └── gdpr.py        # GDPR articles
│   │   ├── evidence.py        # Evidence collection + verification
│   │   └── templates/         # Report template files
│   ├── audit/                 # WORM audit trail ← SPRINT 1
│   │   ├── worm_store.py      # Append-only log storage
│   │   ├── signing.py         # Cryptographic signing of events
│   │   └── verification.py    # Chain integrity verification
│   ├── identity/              # RBAC + SSO integration ← SPRINT 1
│   │   ├── provider.py        # Identity provider abstraction
│   │   ├── roles.py           # Role definitions
│   │   └── middleware.py      # Auth middleware
│   ├── data_pipeline/         # Document ingestion ← SPRINT 2
│   ├── orchestration/         # Model routing + task dispatch ← SPRINT 2
│   ├── governance/            # Policy engine + eval ← SPRINT 3
│   ├── mcp_scanner/           # MCP security scanning ← SPRINT 4
│   ├── airgap/                # Air-gap deployment ← SPRINT 4
│   └── main.py               # Application entry point
├── web/                        # Frontend (React/TypeScript)
│   ├── chat/                  # Agentic chat interface
│   ├── admin/                 # Admin dashboard
│   └── components/            # Shared UI components
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── compliance/            # Compliance-specific tests
├── docs/
│   ├── architecture.md        # Architecture documentation
│   ├── compliance/            # Compliance documentation
│   └── deployment/            # Deployment guides
├── spec/                       # Spec files
│   ├── SPEC.md                # This file
│   └── sprints/               # Per-sprint specs
├── pyproject.toml
└── README.md
```

---

## Success Criteria

### Overall Platform
- [ ] All 7 layers deployed and integrated end-to-end
- [ ] Sub-10 minute deployment with standard configuration
- [ ] Zero external API calls in sovereign/air-gap mode
- [ ] 95%+ uptime for core services (API, inference, governance)

### Sprint 1 — Compliance Foundation
- [ ] WORM audit store: append-only, cryptographically signed, chain integrity verified
- [ ] RBAC: admin, operator, auditor, user roles with scope-limited permissions
- [ ] Compliance engine generates CMMC Level 2 report with evidence mapping
- [ ] Compliance engine generates EU AI Act Article 9-14 report
- [ ] 80%+ test coverage on compliance + audit modules

### Sprint 5 — Production Readiness
- [ ] CMMC 2.0 Level 2 self-certification evidence package complete
- [ ] EU AI Act external audit support documentation complete
- [ ] Air-gapped deployment documented with step-by-step guide
- [ ] SBOM pipeline auto-generating for all releases
- [ ] All tests passing with 80%+ overall coverage
