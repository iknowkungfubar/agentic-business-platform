# Security Policy — TurinTech Agentic Business Platform

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x (development) | Limited — ongoing active development |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Contact: security@turintech.solutions
Response time: Within 48 hours

## Security Practices

### Supply Chain
- All dependencies pinned in lockfile (uv.lock)
- SBOM generated per release via `core.hardening.sbom`
- Dependency updates reviewed monthly

### Authentication
- API key auth with SHA-256 hashing (constant-time comparison)
- Session cookies: httpOnly, secure, sameSite
- MFA required for admin roles

### Audit
- All agent actions logged in WORM audit trail
- Cryptographic chain verification detects tampering
- Log retention: minimum 12 months

### Network
- mTLS for service-to-service communication
- TLS 1.3 for all external endpoints
- Air-gap mode available for disconnected deployments

## Bug Bounty

Not currently active — contact security@turintech.solutions for coordinated disclosure.
