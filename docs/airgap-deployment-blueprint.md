# Air-Gapped Deployment Blueprint

> TurinTech Agentic Business Platform — Deploying in physically or logically isolated environments

## Overview

An air-gapped deployment runs the entire AI platform with zero external network connectivity. No cloud API calls, no telemetry, no model downloads over the wire. This is the deployment mode for defense contractors (CMMC, ITAR), classified government programs, and critical infrastructure operators.

**Key principle:** Design for the air-gap from the start. Retrofitting isolation onto a cloud-dependent system is expensive and fragile. Design every component to work fully offline, then add controlled connectivity as an optional layer.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     AIR-GAPPED BOUNDARY                              │
│  (No physical or logical connection to external networks)            │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  Transfer Zone    │  │  Secure Zone     │  │  Classified Zone  │   │
│  │  (One-way diode)  │  │  (Air-gapped)    │  │  (Air-gapped)     │   │
│  │                   │  │                  │  │                    │   │
│  │  Inbound data     │──►  Platform Core   │  │  Highest class     │   │
│  │  Model bundles    │──►  Inference       │  │  data only         │   │
│  │  Signed updates   │──►  Vector stores   │  │  Separate HW       │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Components Inside the Air-Gap

| Component | Deployment Mode | Notes |
|-----------|----------------|-------|
| **Inference Engine** | llama.cpp / LM Studio | Runs entirely on local GPU/CPU. No API calls to external providers. |
| **Vector Database** | LightRAG / sqlite-vec | Self-contained, no external embedding APIs. Embeddings generated locally. |
| **API Gateway** | Caddy | Reverse proxy with mTLS. No external routing dependencies. |
| **Identity Provider** | ZITADEL / Keycloak | Self-contained SSO with local directory. No federation required. |
| **Audit Store** | WORM SQLite | Local append-only store. Exports via signed bundles. |
| **Agent Control Plane** | ACP CLI + Dashboard | Fully local. Inventory, health, cost, alerts all self-contained. |
| **Monitoring** | Prometheus + Grafana | Local metrics only. No cloud export. |
| **Frontend** | Static HTML + API | No CDN. All assets bundled and served from local. |

### Transfer Zone (Inbound Only)

The transfer zone is the ONLY point where data enters the air-gap. It must enforce:

1. **One-way data flow** — Physical diode or enforced unidirectional gateway
2. **Signed bundles** — All incoming data must be cryptographically signed
3. **Scan before transfer** — Malware scan on all incoming bundles
4. **Verified checksums** — SHA-256 hashes verified before acceptance
5. **Audit log** — Every transfer recorded in WORM audit store

**Transfer types:**

| Transfer | Format | Signing | Frequency |
|----------|--------|---------|-----------|
| Model updates | Signed GGUF bundles | GPG + SHA-256 | As needed (quarterly typical) |
| Policy updates | Signed YAML bundles | GPG | As needed |
| Software patches | Signed OCI bundles | Cosign + SBOM | Monthly |
| Data imports | Encrypted archive | GPG | As needed |
| Audit exports | Signed JSON | Chain signature | Monthly |

---

## 5-Step Deployment Process

### Step 1: Hardware Sizing

| Workload | Minimum | Recommended | Notes |
|----------|---------|-------------|-------|
| Inference (9B models) | 16GB RAM, 8GB VRAM | 32GB RAM, 16GB VRAM | AMD RX 7900 GRE or NVIDIA RTX 4070+ |
| Inference (35B+ models) | 64GB RAM, 24GB VRAM | 128GB RAM, 48GB VRAM | Dual GPU or workstation class |
| Vector store (10K docs) | 16GB RAM, 4 cores | 32GB RAM, 8 cores | SSD required |
| Full platform | 32GB RAM, 8 cores | 64GB RAM, 16 cores | Combined inference + services |
| Air-gapped transfer node | 8GB RAM, 2 cores | 16GB RAM, 4 cores | Diodes need dedicated hardware |

### Step 2: Initial Provisioning

```bash
# 1. Prepare the provisioning media (done on connected machine)
# Download model files
wget https://huggingface.co/models/qwen3.5-9b-deepseek-v4-flash-gguf
# Verify checksums
sha256sum qwen3.5-9b*.gguf > checksums.sha256
gpg --detach-sign checksums.sha256
# Bundle for transfer
tar czf model-bundle.tar.gz *.gguf checksums.sha256 checksums.sha256.sig
# Copy to transfer media (encrypted USB / burned disc)

# 2. On the air-gapped system (after transfer)
# Verify bundle integrity
gpg --verify checksums.sha256.sig checksums.sha256
sha256sum -c checksums.sha256
# Extract
tar xzf model-bundle.tar.gz
# Load models into inference engine
cp *.gguf ~/.lmstudio/models/
# Load platform container images
podman load -i platform-bundle.tar
```

### Step 3: Service Configuration

```yaml
# config.yaml — Air-gapped platform configuration
platform:
  mode: air-gapped  # no external network access
  network:
    egress: blocked
    ingress: local-only
  
security:
  tls: enforced
  mtls: service-to-service
  audit:
    store: worm
    export: signed-bundle
  
inference:
  provider: llama-cpp
  models:
    - path: /models/qwen3.5-9b.gguf
      type: small
    - path: /models/llama-35b.gguf
      type: large
  embedding:
    model: nomic-embed-text-v1.5
    engine: llama-cpp

storage:
  vector: sqlite-vec  # no external vector DB needed
  audit: worm-sqlite
  models: local-filesystem

identity:
  provider: zitadel  # self-contained
  mfa: hardware-token

airgap:
  transfer_zone: /mnt/transfer
  signing_key: /etc/platform/signing-key.gpg
  allowed_transfer_types:
    - model-bundle
    - policy-bundle
    - patch-bundle
```

### Step 4: Verification Checklist

- [ ] All services running with zero external DNS lookups
- [ ] Network egress blocked at OS/firewall level
- [ ] All model inference runs locally (no cloud API calls)
- [ ] Audit events being written to WORM store
- [ ] Identity provider operational (local directory)
- [ ] Model update pipeline tested with signed bundle
- [ ] Degraded-mode operation verified (services handle individual failures)
- [ ] SBOM generated for all platform components
- [ ] Backup/restore procedure tested

### Step 5: Ongoing Operations

| Operation | Frequency | Procedure |
|-----------|-----------|-----------|
| Model updates | Quarterly | Download signed bundle on connected machine, verify signatures, transfer via USB/diode, load into inference engine |
| Policy updates | Monthly | Update policy YAML, sign with GPG, transfer, apply via `acp policy apply` |
| Software patches | Monthly | Build container images on connected air-gapped build server, sign with Cosign, transfer, deploy |
| Audit export | Weekly/monthly | Export signed WORM bundle, transfer out via one-way diode for compliance review |
| Health check | Daily | Review Prometheus/Grafana dashboard (local only) |
| Red-team test | Quarterly | Schedule via ACP red-team module, execute from isolated test network |

---

## Security Controls

### Network Isolation

| Control | Implementation |
|---------|---------------|
| Physical air-gap | No network connectivity between isolated and external networks |
| One-way diode | Hardware data diode for outbound audit exports (optional) |
| Transfer media | Encrypted USB drives with tamper-evident seals |
| Egress blocking | Host firewall denies all outbound traffic; explicit allowlist |
| Ingress restriction | Services bind to 127.0.0.1 or internal VLAN only |

### Cryptographic Controls

| Control | Implementation |
|---------|---------------|
| Bundle signing | GPG (4096-bit RSA) for all transferred bundles |
| Software signing | Cosign for container images; SBOM verification |
| Audit chain | SHA-256 cryptographic chain for all audit events |
| Inter-service | mTLS between all platform components |
| Key management | Local HSM or secure enclave for signing keys |
| PQC readiness | Hybrid TLS 1.3 with X25519 + ML-KEM (FIPS 203) |

### Physical Security

| Control | Implementation |
|---------|---------------|
| Transfer procedure | Two-person integrity for classified transfers |
| Secure boot | UEFI Secure Boot + measured boot (TPM 2.0) |
| Storage encryption | LUKS full-disk encryption on all storage |
| TPE | Tamper-evident seals on transfer media and chassis |

---

## CMMC 2.0 Compliance Mapping

| CMMC Control | Air-Gap Implementation |
|-------------|----------------------|
| AC.1.001 — Authorized access | ZITADEL RBAC + mTLS + hardware MFA |
| AC.1.003 — CUI flow control | Air-gap physically prevents unauthorized CUI exfiltration |
| AU.2.041 — Audit records | WORM audit store with cryptographic chain |
| AU.3.049 — Protect audit info | Append-only SQL triggers + signed logs |
| SC.1.175 — CUI at rest | LUKS encryption + LUKS key management |
| SC.1.176 — CUI in transit | mTLS between all services |
| IA.2.081 — MFA for privileged | Hardware token MFA + local identity provider |
| AI.1.001 — Input validation | Policy engine blocks adversarial inputs |
| AI.3.001 — Output monitoring | WORM audit logs + SIEM integration |
| AI.4.001 — Adversarial testing | Red-team scheduler with quarterly testing |

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Model quality may lag behind cloud | Latest frontier models are cloud-only | Invest in retrieval quality (better RAG beats larger models for most tasks) |
| Slower update cycle | Patches and models delivered via physical media | Design update pipeline at start; batch updates quarterly |
| No real-time threat intel | Air-gap means no live threat feed | Manual threat intel updates via signed bundles |
| Hardware dependency | Must size hardware correctly upfront | Over-provision GPU/CPU by 30-50%; use quantized models |
| No SaaS monitoring | Can't use Datadog, New Relic, etc. | Local Prometheus + Grafana with alerting |
