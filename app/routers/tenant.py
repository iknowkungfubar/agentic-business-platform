"""Tenant resolution endpoint — resolves branding details from custom domain."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.database import _get_engine

router = APIRouter(tags=["tenant"])


@router.get("/api/v1/tenant/resolve")
async def resolve_tenant(domain: str = Query(..., description="Custom domain to resolve")):
    """Unauthenticated endpoint — returns branding details for a tenant's custom domain.

    Used by the frontend's white-labeling system to dynamically apply
    tenant-specific branding (logo, colors) on initial page load.
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, name, slug, logo_url, primary_color_hex, secondary_color_hex
                    FROM organizations
                    WHERE custom_domain = :domain
                    LIMIT 1
                """),
                {"domain": domain},
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Tenant not found for this domain")

            return {
                "tenant_id": row[0],
                "tenant_name": row[1],
                "slug": row[2],
                "logo_url": row[3] or "",
                "primary_color": row[4] or "#10b981",
                "secondary_color": row[5] or "#6366f1",
            }
    finally:
        engine.dispose()
