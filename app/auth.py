"""Authentication — JWT tokens, API key generation, password hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes


# ── Password Hashing (stdlib only — no passlib dependency) ────


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"{salt}:{pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    salt, pwd_hash = stored.split(":", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return hmac.compare_digest(check.hex(), pwd_hash)


# ── JWT Tokens ────────────────────────────────────────────────


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    org_id: int | None = None,
) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": email,
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


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
