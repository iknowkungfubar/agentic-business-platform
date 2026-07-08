"""Unit tests for the MCP security scanner."""

from __future__ import annotations

import json

import pytest

from core.security.mcp_scanner import (
    FindingSeverity,
    MCPScanner,
    ScanTarget,
    Finding,
)


class TestScanTarget:
    def test_parse_full_url(self):
        t = ScanTarget("https://mcp.example.com:8443/v1/health")
        assert t.hostname == "mcp.example.com"
        assert t.port == 8443
        assert t.scheme == "https"
        assert t.path == "/v1/health"
        assert t.is_https is True

    def test_parse_default_http_port(self):
        t = ScanTarget("http://localhost:3000")
        assert t.port == 3000
        assert t.is_https is False

    def test_parse_default_https_port(self):
        t = ScanTarget("https://example.com")
        assert t.port == 443

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            ScanTarget("not-a-url")

    def test_empty_url_raises(self):
        with pytest.raises(ValueError):
            ScanTarget("")

    def test_ipv4_address(self):
        t = ScanTarget("http://127.0.0.1:8080")
        assert t.hostname == "127.0.0.1"
        assert t.port == 8080


class TestMCPScanner:
    def test_scanner_accepts_timeout(self):
        scanner = MCPScanner(timeout=0.5)
        assert scanner.timeout == 0.5

    def test_scanner_default_timeout(self):
        scanner = MCPScanner()
        assert scanner.timeout == 5.0

    def test_print_summary_empty(self):
        scanner = MCPScanner()
        summary = scanner.print_summary([])
        assert "0" in summary

    def test_print_summary_with_results(self):
        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(["http://127.0.0.1:1"])
        summary = scanner.print_summary(results)
        assert "1" in summary

    def test_report_includes_generated_at(self):
        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(["http://127.0.0.1:1"])
        report = scanner.generate_report(results)
        assert "generated_at" in report

    def test_report_json_roundtrip(self, tmp_path):
        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(["http://127.0.0.1:1", "http://127.0.0.1:2"])
        out = tmp_path / "scan.json"
        scanner.export_json(results, str(out))

        with open(out) as f:
            data = json.load(f)
        assert len(data["results"]) == 2


class TestFinding:
    def test_finding_has_all_fields(self):
        f = Finding(
            severity=FindingSeverity.HIGH,
            description="Test finding",
            detail="Detail text",
            recommendation="Fix it",
        )
        assert f.severity == FindingSeverity.HIGH
        assert f.description == "Test finding"
        assert f.detail == "Detail text"
        assert f.recommendation == "Fix it"

    def test_finding_default_severity(self):
        f = Finding(severity=FindingSeverity.INFO, description="Info")
        assert f.severity == FindingSeverity.INFO

    def test_severity_ordering(self):
        """Severity enum should have meaningful ordering."""
        severities = list(FindingSeverity)
        # In order of decreasing severity
        assert severities == [
            FindingSeverity.CRITICAL,
            FindingSeverity.HIGH,
            FindingSeverity.MEDIUM,
            FindingSeverity.LOW,
            FindingSeverity.INFO,
        ]
