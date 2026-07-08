# TurinTech Agentic Business Platform

**Sovereign AI infrastructure for regulated enterprises.**

A production-ready, secure AI platform that bridges enterprise needs with compliant AI implementation — supporting local inference, self-hosted models, full data sovereignty, and air-gap capability.

## Target Markets

- **Defense contractors** — CMMC 2.0 Level 2 compliance (Phase 2: Nov 10, 2026)
- **Government agencies** — Air-gapped, sovereign AI with zero external API calls
- **Regulated enterprises** — EU AI Act (Aug 2026), GDPR, HIPAA
- **Mid-market** — Enterprise-grade AI without the enterprise IT team

## Architecture

```
INTERFACE       — Agentic chat + admin panel + API gateway
ORCHESTRATION   — Intent classifier → model router → task dispatcher → verifier loop
KNOWLEDGE       — Vector DB + graph memory + semantic cache + session memory
DATA PIPELINE   — Ingest → clean → chunk → embed → index → RBAC → audit
GOVERNANCE      — ACP + policy-as-code (OPA) + agent eval + MCP scanner + SBOM
SECURITY        — PKI/mTLS + RBAC + WORM audit + CMMC/EU AI Act evidence
INTERNET CTRL   — Air-gap mode with controlled egress guardrails
```

## Existing Components

| Component | Repo | Role |
|-----------|------|------|
| Agent Control Plane | [agent-control-plane](https://github.com/iknowkungfubar/agent-control-plane) | Agent governance, monitoring, compliance |
| IronSilo | [IronSilo](https://github.com/iknowkungfubar/IronSilo) | Local inference, RAG, memory, proxy |
| HALF | [HALF](https://github.com/iknowkungfubar/HALF) | Multi-agent orchestration, worktree isolation |
| Ring-Fenced RAG | [ring-fenced-rag](https://github.com/iknowkungfubar/ring-fenced-rag) | Zero-trust RAG with RBAC |
| No-Slop Harness | [no-slop-harness](https://github.com/iknowkungfubar/no-slop-harness) | Quality enforcement for agent code |

## Sprint Plan

| Sprint | Focus | Status |
|--------|-------|--------|
| S1 | Compliance Foundation (WORM audit + RBAC + compliance engine) | ✅ Built |
| S2 | Data Pipeline + Model Router | 🔜 Next |
| S3 | Policy-as-Code + Agent Evaluation | 📋 Planned |
| S4 | MCP Scanner + Air-Gap + Internet Gateway | 📋 Planned |
| S5 | Enterprise Chat + SBOM + Production Hardening | 📋 Planned |

## Quick Start

```bash
# Clone the platform repo
git clone https://github.com/iknowkungfubar/agentic-business-platform.git
cd agentic-business-platform

# Compliance engine is in the acp/ submodule
cd acp
uv sync --group dev
uv run python -m pytest tests/ -q

# Generate a CMMC compliance report
uv run acp compliance report --framework CMMC-2.0 --output report.json
```

## License

MIT — see [LICENSE](LICENSE) for details.
