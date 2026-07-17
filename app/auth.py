"""Authentication — OIDC/SSO with JWKS validation, PBKDF2 fallback.

Supports two modes:
1. OIDC (production): validates JWTs signed by an external Identity Provider
   (Keycloak, ZITADEL) using published JWKS keys. Configure via OIDC_ env vars.
2. PBKDF2 (fallback/dev): local password hashing with built-in JWT signing.
   Used when no OIDC provider is configured.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.constants import Algorithms

from app.config import settings

# ── PBKDF2 (Fallback Auth) ────────────────────────────────────

SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"{salt}:{pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    salt, pwd_hash = stored.split(":", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return hmac.compare_digest(check.hex(), pwd_hash)


# ── JWT Tokens (Local) ────────────────────────────────────────


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    org_id: int | None = None,
) -> str:
    """Create a local JWT access token."""
    payload = {
        "sub": email,
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": "turin-platform",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a local JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── OIDC / JWKS (Enterprise SSO) ──────────────────────────────

# Cache for JWKS keys
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0}
_JWKS_CACHE_TTL = 300  # 5 minutes


async def _fetch_jwks() -> list[dict[str, Any]] | None:
    """Fetch and cache JWKS keys from the OIDC provider."""
    oidc_url = settings.oidc_jwks_url
    if not oidc_url:
        return None

    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL:
        return _jwks_cache["keys"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(oidc_url)
            if resp.status_code == 200:
                data = resp.json()
                _jwks_cache["keys"] = data.get("keys", [])
                _jwks_cache["fetched_at"] = now
                return _jwks_cache["keys"]
    except Exception:
        pass

    # Return stale cache on failure rather than breaking auth
    return _jwks_cache["keys"]


async def validate_oidc_token(token: str) -> dict[str, Any] | None:
    """Validate a JWT using OIDC JWKS keys.

    Returns the token payload if valid, None otherwise.
    Falls back to local decode if no OIDC provider is configured.
    """
    oidc_url = settings.oidc_jwks_url
    if not oidc_url:
        # No OIDC configured — try local decode
        return decode_token(token)

    keys = await _fetch_jwks()
    if not keys:
        return None

    # Try each key until one validates
    for key_data in keys:
        try:
            return jwt.decode(
                token,
                key_data,
                algorithms=[Algorithms.RS256, Algorithms.RS384, Algorithms.RS512],
                options={"verify_aud": False},
            )
        except JWTError:
            continue

    return None


def get_oidc_discovery_document() -> dict[str, Any] | None:
    """Get the OIDC discovery document for this platform."""
    oidc_issuer = settings.oidc_issuer
    if not oidc_issuer:
        return None

    base = f"{oidc_issuer}"
    return {
        "issuer": oidc_issuer,
        "authorization_endpoint": f"{base}/protocol/openid-connect/auth",
        "token_endpoint": f"{base}/protocol/openid-connect/token",
        "jwks_uri": settings.oidc_jwks_url or f"{base}/protocol/openid-connect/certs",
        "response_types_supported": ["code", "id_token", "token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


# ── API Keys ──────────────────────────────────────────────────


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key with prefix and hash."""
    raw = f"tp_{secrets.token_urlsafe(32)}"
    prefix = raw[:10]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash, prefix


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    return hmac.compare_digest(hashlib.sha256(raw_key.encode()).hexdigest(), stored_hash)
