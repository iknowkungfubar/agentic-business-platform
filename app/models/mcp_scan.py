"""MCP Scan result model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import Base


class MCPScanResult(Base):
    """Persistent storage for MCP security scan results."""

    __tablename__ = "mcp_scan_results"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(512), nullable=False)
    reachable = Column(Integer, default=0)
    status_code = Column(Integer, nullable=True)
    is_https = Column(Integer, default=0)
    requires_auth = Column(Integer, default=0)
    finding_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    summary_json = Column(Text, default="{}")
    scanned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
