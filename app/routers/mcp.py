"""MCP scanner endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.routers import require_role

router = APIRouter(tags=["mcp"])


class ScanMCPRequest(BaseModel):
    url: str
    timeout: float = 5.0


@router.post("/scan-mcp")
async def scan_mcp(
    req: ScanMCPRequest,
    user: dict = Depends(require_role("operator")),
):
    from core.security.mcp_scanner import MCPScanner  # noqa: PLC0415

    scanner = MCPScanner(timeout=req.timeout)
    try:
        result = scanner.scan(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "url": result.url,
        "reachable": result.reachable,
        "status_code": result.status_code,
        "is_https": result.is_https,
        "requires_auth": result.requires_auth,
        "findings": [
            {"severity": f.severity.value, "description": f.description, "recommendation": f.recommendation}
            for f in result.findings
        ],
    }
