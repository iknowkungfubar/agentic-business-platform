"""Shared router dependencies — auth dependencies and security helpers."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import validate_oidc_token, verify_api_key
from app.database import get_db, set_tenant_context
from app.models import APIKey, User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """Extract and validate the current user from JWT or API key.

    Supports:
    - OIDC JWTs (production SSO with Keycloak/ZITADEL)
    - Local JWTs (development/fallback)
    - API keys (programmatic access)
    """
    if x_api_key:
        db = next(get_db())
        key_prefix = x_api_key[:10]
        stored = (
            db.query(APIKey)
            .filter(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == 1,
            )
            .first()
        )
        if stored and verify_api_key(x_api_key, stored.key_hash):
            user = db.query(User).filter(User.id == stored.user_id).first()
            if user:
                return {
                    "sub": user.email,
                    "user_id": user.id,
                    "org_id": user.organization_id,
                    "role": user.role,
                }
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Try OIDC validation first, fall back to local decode
    payload = await validate_oidc_token(credentials.credentials)
    if payload:
        set_tenant_context(payload.get("org_id"))
        return payload

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(role: str):
    """Dependency factory: require a minimum role."""

    def checker(user: dict = Depends(get_current_user)):
        role_hierarchy = {"viewer": 0, "operator": 1, "auditor": 1, "admin": 2}
        if role_hierarchy.get(user.get("role", "viewer"), 0) < role_hierarchy.get(role, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker
