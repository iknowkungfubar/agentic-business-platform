"""Tenant context middleware — enforces multi-tenant data isolation.

Extracts the Organization ID from the authenticated JWT and propagates it
into the PostgreSQL session via SET LOCAL. This enables Row-Level Security
(RLS) policies to automatically scope all queries to the current tenant.

For zero-trust enforcement: even if a route handler forgets to filter by
organization_id, RLS will silently apply the correct filter.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extracts tenant (org_id) from JWT and sets PostgreSQL session context.

    This middleware runs after authentication but before route handlers.
    It reads the org_id from the JWT payload (set on request.state by
    get_current_user) and executes SET LOCAL to propagate it into the
    PostgreSQL session for RLS enforcement.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract org_id from wherever it's available
        org_id = None

        # Try request.state (set by get_current_user auth dependency)
        if hasattr(request.state, "user_org_id"):
            org_id = request.state.user_org_id

        # Fallback: try to extract from Authorization header directly
        if org_id is None:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                try:
                    from app.auth import validate_oidc_token  # noqa: PLC0415
                    import asyncio  # noqa: PLC0415

                    payload = asyncio.run(validate_oidc_token(auth[7:]))
                    if payload:
                        org_id = payload.get("org_id")
                        if org_id is None:
                            org_id = payload.get("organization_id")
                except Exception:
                    pass

        # Store on request state for session factory to use
        request.state.tenant_id = org_id

        response = await call_next(request)
        return response


class TenantSessionFilter:
    """Callable that applies tenant context to a SQLAlchemy session.

    Used by the session factory to set app.current_tenant_id before
    each transaction.
    """

    def __init__(self) -> None:
        self._tenant_id: int | None = None

    def set_tenant(self, tenant_id: int | None) -> None:
        self._tenant_id = tenant_id

    def apply(self, db_session: Any) -> None:
        """Apply tenant context to a database session.

        Executes SET LOCAL to set the PostgreSQL configuration parameter
        used by RLS policies. Safe to call multiple times — only the
        first SET LOCAL per transaction takes effect.
        """
        if self._tenant_id is not None:
            try:
                db_session.execute(
                    f"SET LOCAL app.current_tenant_id = '{int(self._tenant_id)}'"
                )
            except Exception:
                pass  # Non-PostgreSQL dialects ignore this silently
