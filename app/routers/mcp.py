"""MCP scanner endpoints — scan servers and retrieve results."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import MCPScanResult, get_db
from app.pagination import PaginationParams, paginate
from app.routers import get_current_user, require_role

router = APIRouter(tags=["mcp"])


class ScanMCPRequest(BaseModel):
    url: str
    timeout: float = 5.0


@router.post("/scan-mcp")
async def scan_mcp(
    req: ScanMCPRequest,
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    """Scan an MCP server for security issues and store the result."""
    from core.security.mcp_scanner import FindingSeverity, MCPScanner  # noqa: PLC0415

    scanner = MCPScanner(timeout=req.timeout)
    try:
        result = scanner.scan(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    findings_data = [
        {"severity": f.severity.value, "description": f.description, "recommendation": f.recommendation}
        for f in result.findings
    ]
    critical = sum(1 for f in result.findings if f.severity == FindingSeverity.CRITICAL)
    high = sum(1 for f in result.findings if f.severity == FindingSeverity.HIGH)

    # Persist the scan result
    scan_record = MCPScanResult(
        url=result.url,
        reachable=int(result.reachable),
        status_code=result.status_code,
        is_https=int(result.is_https),
        requires_auth=int(result.requires_auth),
        finding_count=len(result.findings),
        critical_count=critical,
        high_count=high,
        summary_json=json.dumps(findings_data),
        scanned_by=user.get("user_id"),
        organization_id=user.get("org_id"),
    )
    db.add(scan_record)
    db.commit()

    return {
        "scan_id": scan_record.id,
        "url": result.url,
        "reachable": result.reachable,
        "status_code": result.status_code,
        "is_https": result.is_https,
        "requires_auth": result.requires_auth,
        "findings": findings_data,
    }


@router.get("/mcp/results")
async def list_scan_results(
    page_params: PaginationParams = Depends(),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List previous MCP scan results."""
    query = (
        db.query(MCPScanResult)
        .filter(MCPScanResult.organization_id == user.get("org_id"))
        .order_by(MCPScanResult.id.desc())
    )
    total = query.count()
    results = query.offset(page_params.offset).limit(page_params.page_size).all()
    items = [
        {
            "id": r.id,
            "url": r.url,
            "reachable": bool(r.reachable),
            "status_code": r.status_code,
            "finding_count": r.finding_count,
            "critical_count": r.critical_count,
            "high_count": r.high_count,
            "scanned_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in results
    ]
    return paginate(items, total, page_params)
