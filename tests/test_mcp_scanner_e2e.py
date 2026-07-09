"""E2E tests for the MCP security scanner."""

from __future__ import annotations

import json

import pytest

from core.security.mcp_scanner import (
    FindingSeverity,
    MCPScanner,
    ScanTarget,
)


class TestMCPScannerE2E:
    """Full MCP scanning workflow."""

    def test_mcp_scanner_detects_unreachable_server(self):
        """A server that doesn't exist should report accordingly."""
        scanner = MCPScanner(timeout=1.0)
        result = scanner.scan("http://127.0.0.1:1")
        assert result.url == "http://127.0.0.1:1"
        assert result.reachable is False
        # Should have at least one finding about unreachability
        assert len(result.findings) > 0
        critical_findings = [
            f for f in result.findings if f.severity == FindingSeverity.CRITICAL
        ]
        assert any("unreachable" in f.description.lower() for f in critical_findings)

    def test_mcp_scanner_produces_report(self):
        """Scanner should produce a structured report."""
        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(
            [
                "http://127.0.0.1:1",
                "http://127.0.0.1:2",
            ]
        )
        report = scanner.generate_report(results)

        assert "scan_summary" in report
        assert report["scan_summary"]["total"] == 2
        assert report["scan_summary"]["reachable"] == 0

    def test_scan_target_parsing(self):
        """ScanTarget should parse URLs correctly."""
        target = ScanTarget("https://mcp.example.com:8443/v1")
        assert target.hostname == "mcp.example.com"
        assert target.port == 8443
        assert target.scheme == "https"
        assert target.is_https is True

    def test_scan_target_http_detection(self):
        """ScanTarget should detect non-HTTPS."""
        target = ScanTarget("http://insecure.example.com")
        assert target.is_https is False

    def test_scan_result_json_export(self, tmp_path):
        """Scan result should export to JSON."""
        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(["http://127.0.0.1:1"])
        out = tmp_path / "scan.json"
        scanner.export_json(results, str(out))

        with open(out) as f:
            data = json.load(f)
        assert "scan_summary" in data
        assert "results" in data
        assert data["scan_summary"]["total"] == 1

    def test_mcp_scanner_rejects_invalid_urls(self):
        """Scanner should reject clearly invalid URLs."""
        scanner = MCPScanner()
        with pytest.raises(ValueError, match="Invalid URL"):
            scanner.scan("not-a-url")

    def test_empty_targets_list(self):
        """Empty targets should produce empty results."""
        scanner = MCPScanner()
        results = scanner.scan_multi([])
        assert len(results) == 0
