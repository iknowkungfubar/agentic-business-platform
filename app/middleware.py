"""Middleware — rate limiter with per-org support."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter with per-organization isolation.

    - Unauthenticated requests are keyed by client IP.
    - Authenticated requests are keyed by organization ID (if available)
      or user ID, providing per-tenant rate limiting.

    Can be disabled via DISABLE_RATE_LIMIT=1 for testing.
    """

    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
            return await call_next(request)

        if request.url.path in ("/auth/login", "/auth/register", "/api/v1/auth/login", "/api/v1/auth/register"):
            # Use organization as rate-limit key for authenticated requests
            # Fall back to IP for unauthenticated
            client_ip = request.client.host if request.client else "unknown"
            limit_key = client_ip

            # Try to extract org from auth header
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                from app.auth import decode_token  # noqa: PLC0415

                payload = decode_token(auth[7:])
                if payload:
                    org_id = payload.get("org_id")
                    if org_id:
                        limit_key = f"org:{org_id}"
                    else:
                        limit_key = f"user:{payload.get('user_id', client_ip)}"

            now = datetime.now(UTC).timestamp()

            if limit_key not in self._requests:
                self._requests[limit_key] = []

            cutoff = now - self.window_seconds
            self._requests[limit_key] = [t for t in self._requests[limit_key] if t > cutoff]

            if len(self._requests[limit_key]) >= self.max_requests:
                from fastapi.responses import JSONResponse  # noqa: PLC0415

                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please wait before trying again."},
                    headers={
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Reset": str(int(now + self.window_seconds)),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            self._requests[limit_key].append(now)

        return await call_next(request)
