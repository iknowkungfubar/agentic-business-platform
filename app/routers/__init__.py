"""Shared router dependencies — auth, rate limiter, app state."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import decode_token, verify_api_key
from app.db import APIKey, User, get_db

security = HTTPBearer(auto_error=False)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for auth endpoints."""

    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        # Allow disabling via env var for testing
        if os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
            return await call_next(request)

        # Only rate-limit auth endpoints
        if request.url.path in ("/auth/login", "/auth/register"):
            client_ip = request.client.host if request.client else "unknown"
            now = datetime.now(UTC).timestamp()

            if client_ip not in self._requests:
                self._requests[client_ip] = []

            # Clean old entries
            cutoff = now - self.window_seconds
            self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]

            if len(self._requests[client_ip]) >= self.max_requests:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please wait before trying again."},
                )

            self._requests[client_ip].append(now)

        return await call_next(request)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """Extract and validate the current user from JWT or API key."""
    db = next(get_db())

    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            return payload

    if x_api_key:
        # Look up API key
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

    raise HTTPException(status_code=401, detail="Not authenticated")


def require_role(role: str):
    """Dependency factory: require a minimum role."""

    def checker(user: dict = Depends(get_current_user)):
        role_hierarchy = {"viewer": 0, "operator": 1, "auditor": 1, "admin": 2}
        if role_hierarchy.get(user.get("role", "viewer"), 0) < role_hierarchy.get(role, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker
