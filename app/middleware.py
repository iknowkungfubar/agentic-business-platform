"""Middleware — Redis Token Bucket rate limiter with per-tenant quotas."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class TokenBucketRateLimiter(BaseHTTPMiddleware):
    """Redis-backed token bucket rate limiter with per-tenant isolation.

    Algorithm:
    - Each tenant (org) has a bucket with `capacity` tokens (burst limit)
    - Tokens refill at `refill_rate` tokens per second
    - If no tokens remain, the request is denied with 429
    - Tokens are stored in Redis as a sorted set for distributed counting
    - Falls back to in-memory counting when Redis is unavailable

    Configuration (from app.config or env):
    - RATE_LIMIT_MAX: max requests per minute per tenant (default: 100)
    - RATE_LIMIT_BURST: burst capacity (default: 150)
    """

    def __init__(
        self,
        app: Any,
        capacity: int | None = None,
        refill_rate: float | None = None,
        refill_interval: int = 60,
    ):
        super().__init__(app)
        self.capacity = capacity or int(os.getenv("RATE_LIMIT_MAX", settings.rate_limit_max))
        self.refill_rate = refill_rate or (self.capacity / (refill_interval or 60))
        self.refill_interval = refill_interval
        # In-memory fallback: {key: {"tokens": float, "last_refill": float}}
        self._buckets: dict[str, dict[str, float]] = {}

    def _get_redis(self):
        """Get a Redis client (returns None if unavailable)."""
        try:
            from redis.asyncio import Redis  # noqa: PLC0415

            return Redis.from_url(
                f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/1",
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception:
            return None

    def _get_limit_key(self, request: Request) -> str | None:
        """Extract the rate limit key from the request.

        Returns:
            - "org:{org_id}" for authenticated requests
            - "ip:{client_ip}" for unauthenticated requests
            - None for paths that should not be rate-limited
        """
        # Skip metrics and health endpoints
        if request.url.path in ("/health", "/metrics", "/health/ready", "/health/deep"):
            return None

        # Try to extract org from auth header
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.auth import decode_token  # noqa: PLC0415

                payload = decode_token(auth[7:])
                if payload:
                    org_id = payload.get("org_id")
                    if org_id:
                        return f"org:{org_id}"
                    user_id = payload.get("user_id")
                    if user_id:
                        return f"user:{user_id}"
            except Exception:
                pass

        # Fall back to client IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _check_token_bucket(self, key: str) -> tuple[bool, float]:
        """Check the token bucket for a given key.

        Returns:
            (allowed: bool, retry_after_seconds: float)
        """
        now = time.time()

        if key not in self._buckets:
            self._buckets[key] = {"tokens": float(self.capacity), "last_refill": now}

        bucket = self._buckets[key]
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            float(self.capacity),
            bucket["tokens"] + elapsed * self.refill_rate,
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True, 0.0

        # Calculate retry-after based on refill rate
        retry_after = (1.0 - bucket["tokens"]) / self.refill_rate
        return False, max(retry_after, 1.0)

    async def _check_redis_token_bucket(self, key: str) -> tuple[bool, float]:
        """Check the token bucket using Redis (distributed)."""
        redis = await self._get_redis()
        if not redis:
            return self._check_token_bucket(key)

        try:
            now = time.time()
            bucket_key = f"rate_limit:{key}"

            # Lua script for atomic token bucket check
            script = """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])

            local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket[1]) or capacity
            local last_refill = tonumber(bucket[2]) or 0

            local elapsed = now - last_refill
            tokens = math.min(capacity, tokens + elapsed * refill_rate)
            last_refill = now

            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
                redis.call('EXPIRE', key, 60)
                return {1, 0}
            else
                local retry_after = math.ceil((1 - tokens) / refill_rate)
                return {0, retry_after}
            end
            """
            import hashlib  # noqa: PLC0415

            sha = hashlib.sha1(script.encode()).hexdigest()
            try:
                result = await redis.evalsha(sha, 1, bucket_key, str(self.capacity), str(self.refill_rate), str(now))
            except Exception:
                result = await redis.eval(script, 1, bucket_key, str(self.capacity), str(self.refill_rate), str(now))

            allowed = bool(result[0])
            retry_after = float(result[1]) if result[1] else 1.0
            return allowed, retry_after
        except Exception:
            return self._check_token_bucket(key)
        finally:
            await redis.aclose()

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
            return await call_next(request)

        limit_key = self._get_limit_key(request)
        if limit_key is None:
            return await call_next(request)

        allowed, retry_after = await self._check_redis_token_bucket(limit_key)

        if not allowed:
            from fastapi.responses import JSONResponse  # noqa: PLC0415

            now_ts = int(datetime.now(UTC).timestamp())
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Please retry after {int(retry_after)} seconds.",
                        "status_code": 429,
                    }
                },
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(self.capacity),
                    "X-RateLimit-Reset": str(now_ts + int(retry_after)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return await call_next(request)
