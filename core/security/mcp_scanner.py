"""MCP security scanner — probes MCP server endpoints for security issues.

Checks for:
- Reachability (server responds)
- HTTPS enforcement
- Authentication requirements
- CORS configuration
- Server version disclosure
- Common misconfiguration patterns
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class FindingSeverity(str, Enum):
    """Severity of a security finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    """A single security finding from scanning an MCP server."""

    severity: FindingSeverity
    description: str
    detail: str = ""
    recommendation: str = ""


@dataclass
class ScanTarget:
    """A target MCP server to scan."""

    url: str
    hostname: str = ""
    port: int = 0
    scheme: str = ""
    path: str = ""

    def __post_init__(self):
        parsed = urlparse(self.url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {self.url}")
        self.hostname = parsed.hostname or ""
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.scheme = parsed.scheme
        self.path = parsed.path or "/"

    @property
    def is_https(self) -> bool:
        return self.scheme == "https"


@dataclass
class ScanResult:
    """Result of scanning a single MCP server."""

    url: str
    reachable: bool = False
    status_code: int | None = None
    is_https: bool = False
    requires_auth: bool | None = None
    server_header: str = ""
    findings: list[Finding] = field(default_factory=list)
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MCPScanner:
    """Scans MCP server endpoints for security issues."""

    # Known unsafe MCP server header patterns
    _UNSAFE_SERVERS = ["nginx/1.18", "apache/2.4.6", "Microsoft-IIS/8.5"]

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def scan(self, url: str) -> ScanResult:
        """Scan a single MCP server URL.

        Args:
            url: The MCP server URL to scan.

        Returns:
            ScanResult with findings.

        Raises:
            ValueError: If the URL is invalid.

        """
        target = ScanTarget(url)
        result = ScanResult(url=url, is_https=target.is_https)

        result.findings.append(
            Finding(
                severity=FindingSeverity.INFO,
                description=f"Scanning MCP server at {url}",
                detail=f"Host: {target.hostname}, Port: {target.port}, Scheme: {target.scheme}",
            )
        )

        # Check HTTPS
        if not target.is_https:
            result.findings.append(
                Finding(
                    severity=FindingSeverity.HIGH,
                    description="MCP server does not use HTTPS",
                    detail="Plain HTTP connections are vulnerable to MITM attacks and data interception",
                    recommendation="Enforce HTTPS with a valid TLS certificate for all MCP endpoints",
                )
            )

        # Probe the server
        try:
            req = urllib.request.Request(url, method="GET")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            resp = urllib.request.urlopen(req, timeout=self.timeout, context=ctx)
            result.reachable = True
            result.status_code = resp.status
            result.server_header = resp.headers.get("Server", "")

            # Check for auth requirement
            www_auth = resp.headers.get("WWW-Authenticate", "")
            result.requires_auth = bool(www_auth)

            if not www_auth:
                result.findings.append(
                    Finding(
                        severity=FindingSeverity.HIGH,
                        description="MCP server does not require authentication",
                        detail="No WWW-Authenticate header found. Server may be accessible without credentials",
                        recommendation="Enable authentication (API key, OAuth, or mTLS) for all MCP endpoints",
                    )
                )
            else:
                result.findings.append(
                    Finding(
                        severity=FindingSeverity.INFO,
                        description=f"Authentication required: {www_auth}",
                    )
                )

            # Check server version disclosure
            if result.server_header:
                for unsafe in self._UNSAFE_SERVERS:
                    if unsafe in result.server_header.lower():
                        result.findings.append(
                            Finding(
                                severity=FindingSeverity.MEDIUM,
                                description=f"Known vulnerable server version: {result.server_header}",
                                detail=f"Server header reveals {result.server_header}, which has known vulnerabilities",
                                recommendation="Update to the latest version or hide server version information",
                            )
                        )
                        break
                else:
                    result.findings.append(
                        Finding(
                            severity=FindingSeverity.INFO,
                            description=f"Server: {result.server_header}",
                        )
                    )

            # Check for CORS misconfiguration
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            if acao == "*":
                result.findings.append(
                    Finding(
                        severity=FindingSeverity.MEDIUM,
                        description="MCP server has permissive CORS policy",
                        detail="Access-Control-Allow-Origin: * allows any website to make requests to this server",
                        recommendation="Restrict CORS to specific trusted origins instead of using wildcard",
                    )
                )

        except urllib.error.HTTPError as e:
            # Server responded with an error — it's reachable
            result.reachable = True
            result.status_code = e.code
            result.server_header = e.headers.get("Server", "")

            # 401/403 means auth is required
            if e.code in (401, 403):
                result.requires_auth = True
                www_auth = e.headers.get("WWW-Authenticate", "")
                result.findings.append(
                    Finding(
                        severity=FindingSeverity.INFO,
                        description=f"Authentication required (HTTP {e.code})",
                        detail=f"WWW-Authenticate: {www_auth}" if www_auth else "Access denied",
                    )
                )

        except urllib.error.URLError:
            result.reachable = False
            result.findings.append(
                Finding(
                    severity=FindingSeverity.CRITICAL,
                    description="MCP server is unreachable",
                    detail="Server did not respond within the timeout period",
                    recommendation="Verify the server is running and the URL is correct",
                )
            )

        return result

    def scan_multi(self, urls: list[str]) -> list[ScanResult]:
        """Scan multiple MCP server URLs.

        Args:
            urls: List of MCP server URLs to scan.

        Returns:
            List of ScanResult objects.

        """
        return [self.scan(url) for url in urls]

    def generate_report(self, results: list[ScanResult]) -> dict[str, Any]:
        """Generate a structured report from scan results.

        Args:
            results: List of ScanResult objects.

        Returns:
            Dict with summary and per-server findings.

        """
        total = len(results)
        reachable = sum(1 for r in results if r.reachable)
        unreachable = total - reachable
        has_auth = sum(1 for r in results if r.requires_auth)
        no_auth = sum(1 for r in results if r.reachable and not r.requires_auth)
        has_https = sum(1 for r in results if r.is_https)

        all_findings: list[dict] = []
        for result in results:
            for finding in result.findings:
                all_findings.append(
                    {
                        "url": result.url,
                        "severity": finding.severity.value,
                        "description": finding.description,
                        "detail": finding.detail,
                        "recommendation": finding.recommendation,
                    }
                )

        # Count by severity
        severity_counts: dict[str, int] = {}
        for f in all_findings:
            sev = f["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "scan_summary": {
                "total": total,
                "reachable": reachable,
                "unreachable": unreachable,
                "with_auth": has_auth,
                "without_auth": no_auth,
                "with_https": has_https,
                "severity_counts": severity_counts,
            },
            "results": [
                {
                    "url": r.url,
                    "reachable": r.reachable,
                    "status_code": r.status_code,
                    "is_https": r.is_https,
                    "requires_auth": r.requires_auth,
                    "server_header": r.server_header,
                    "findings": [
                        {
                            "severity": f.severity.value,
                            "description": f.description,
                            "detail": f.detail,
                            "recommendation": f.recommendation,
                        }
                        for f in r.findings
                    ],
                }
                for r in results
            ],
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def export_json(self, results: list[ScanResult], output_path: str | Path) -> None:
        """Export scan results to a JSON file."""
        report = self.generate_report(results)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    def print_summary(self, results: list[ScanResult]) -> str:
        """Generate a human-readable summary of scan results."""
        report = self.generate_report(results)
        summary = report["scan_summary"]

        lines = [
            "=== MCP Security Scan Summary ===",
            f"Total servers scanned: {summary['total']}",
            f"Reachable: {summary['reachable']}",
            f"Unreachable: {summary['unreachable']}",
            f"With authentication: {summary['with_auth']}",
            f"Without authentication: {summary['without_auth']}",
            f"Using HTTPS: {summary['with_https']}",
            "",
            "Findings by severity:",
        ]

        for sev in ("critical", "high", "medium", "low", "info"):
            count = summary["severity_counts"].get(sev, 0)
            if count > 0:
                lines.append(f"  {sev.upper()}: {count}")

        return "\n".join(lines)
