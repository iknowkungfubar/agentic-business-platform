"""Authentication module — JWT tokens, password hashing, API key management."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class TokenPayload(BaseModel):
    sub: str  # email
    user_id: int
    org_id: int | None = None
    role: str = "viewer"
    exp: datetime | None = None


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt.

    Uses hashlib with PBKDF2-HMAC-SHA256 for secure password storage.
    """
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt, pwd_hash = stored.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100000)
        return hmac.compare_digest(computed.hex(), pwd_hash)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int, email: str, role: str = "viewer", org_id: int | None = None) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "user_id": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash, key_prefix).
    """
    raw = f"tp_{secrets.token_hex(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:10]
    return raw, key_hash, key_prefix


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    computed = hashlib.sha256(raw_key.encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)
