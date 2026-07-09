"""API Key management endpoints — generate, list, revoke scoped API keys."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import generate_api_key, verify_api_key
from app.database import get_db
from app.models import APIKey
from app.models.user import UserRole
from app.routers import RequireRole, get_current_user

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


class CreateAPIKeyRequest(BaseModel):
    name: str = ""
    scopes: list[str] = ["chat:write"]
    expires_in_days: int = 365


@router.post("")
async def create_api_key(
    req: CreateAPIKeyRequest,
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Generate a new scoped API key. Raw key is shown only once."""
    raw, key_hash, key_prefix = generate_api_key()
    expires_at = datetime.now(UTC) + timedelta(days=req.expires_in_days)

    api_key = APIKey(
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=req.name,
        user_id=user["user_id"],
        organization_id=user.get("org_id"),
        scopes=json.dumps(req.scopes),
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()

    return {
        "api_key": raw,
        "key_prefix": key_prefix,
        "name": req.name,
        "scopes": req.scopes,
        "expires_at": expires_at.isoformat(),
        "warning": "Store this key securely — it will not be shown again.",
    }


@router.get("")
async def list_api_keys(
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN)),
    db: Session = Depends(get_db),
):
    """List all API keys for the organization."""
    keys = (
        db.query(APIKey)
        .filter(
            APIKey.organization_id == user.get("org_id"),
        )
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return [
        {
            "id": k.id,
            "key_prefix": k.key_prefix,
            "name": k.name,
            "scopes": json.loads(k.scopes) if k.scopes else [],
            "is_active": bool(k.is_active),
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in keys
    ]


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN)),
    db: Session = Depends(get_db),
):
    """Revoke an API key by setting it inactive."""
    key = (
        db.query(APIKey)
        .filter(
            APIKey.id == key_id,
            APIKey.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = 0
    db.commit()
    return {"status": "revoked", "key_prefix": key.key_prefix}
