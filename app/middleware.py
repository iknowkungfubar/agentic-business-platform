"""Middleware — rate limiter and other ASGI middleware."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for auth endpoints.

    Applies a sliding-window limit to /auth/login and /auth/register.
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

        if request.url.path in ("/auth/login", "/auth/register"):
            client_ip = request.client.host if request.client else "unknown"
            now = datetime.now(UTC).timestamp()

            if client_ip not in self._requests:
                self._requests[client_ip] = []

            cutoff = now - self.window_seconds
            self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]

            if len(self._requests[client_ip]) >= self.max_requests:
                from fastapi.responses import JSONResponse  # noqa: PLC0415

                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please wait before trying again."},
                )

            self._requests[client_ip].append(now)

        return await call_next(request)
