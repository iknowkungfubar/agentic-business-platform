"""Auth endpoints — register, login, API key management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    generate_api_key,
    get_oidc_discovery_document,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import APIKey, Organization, User
from app.routers import get_current_user, require_role

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""
    org_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = None
    if req.org_name:
        org = Organization(name=req.org_name, slug=req.org_name.lower().replace(" ", "-"))
        db.add(org)
        db.flush()

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        organization_id=org.id if org else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=user.organization_id,
    )
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "role": user.role, "org_id": user.organization_id},
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=user.organization_id,
    )
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "role": user.role, "org_id": user.organization_id},
    )


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/.well-known/openid-configuration")
async def oidc_discovery():
    """OIDC discovery document — enables SSO provider auto-configuration."""
    doc = get_oidc_discovery_document()
    if not doc:
        return {"error": "OIDC not configured", "note": "Set OIDC_JWKS_URL and OIDC_ISSUER env vars"}
    return doc


@router.post("/api-key")
async def create_api_key(
    name: str = "",
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    raw, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
        user_id=user["user_id"],
        organization_id=user.get("org_id"),
    )
    db.add(api_key)
    db.commit()
    return {"api_key": raw, "key_prefix": key_prefix, "name": name}
