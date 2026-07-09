"""Integration tests for the CLI and API."""

from __future__ import annotations

import json

import pytest

from app.cli import main as cli_main


class TestCLIIntegration:
    """Tests for the CLI entry point."""

    def test_cli_classify(self):
        """CLI classify should return JSON with intent."""
        exit_code = cli_main(["classify", "What is the capital of France?"])
        assert exit_code == 0

    def test_cli_route(self):
        """CLI route should return JSON with intent and model tier."""
        exit_code = cli_main(["route", "def hello():\n    pass"])
        assert exit_code == 0

    def test_cli_evaluate(self):
        """CLI evaluate should return JSON with policy decision."""
        action = json.dumps({"action_type": "data_access", "resource_type": "cui", "authorized": False})
        exit_code = cli_main(["evaluate", action])
        assert exit_code == 0

    def test_cli_ingest_file_not_found(self, tmp_path):
        """CLI ingest should fail gracefully on missing file."""
        with pytest.raises(SystemExit):
            cli_main(["ingest", "/nonexistent/file.txt"])

    def test_cli_sbom(self, tmp_path):
        """CLI sbom should generate output."""
        out = tmp_path / "test_sbom.json"
        exit_code = cli_main(["sbom", "--output", str(out)])
        assert exit_code == 0
        assert out.exists()

    def test_cli_scan_mcp(self):
        """CLI scan-mcp should handle unreachable servers."""
        exit_code = cli_main(["scan-mcp", "http://127.0.0.1:1"])
        assert exit_code == 0

    def test_cli_no_args_shows_help(self):
        """CLI with no args should show help and return 0."""
        exit_code = cli_main([])
        assert exit_code == 0


class TestAPIIntegration:
    """Tests for the API server endpoints."""

    def test_api_health(self):
        """Health endpoint should return OK."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_api_classify(self):
        """Classify endpoint should return intent."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/classify", json={"text": "Summarize this report"})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "summarization"

    def test_api_route(self):
        """Route endpoint should return model tier."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/route", json={"text": "def foo(): pass"})
        assert response.status_code == 200
        data = response.json()
        assert data["model_tier"] == "t3"

    def test_api_evaluate(self):
        """Evaluate endpoint should return policy decision."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        action = {"action_type": "data_access", "resource_type": "cui", "authorized": False}
        response = client.post("/evaluate", json={"action": action})
        assert response.status_code == 200
        data = response.json()
        assert data["effect"] == "deny"

    def test_api_scan_mcp(self):
        """Scan MCP endpoint should handle unreachable servers."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/scan-mcp", json={"url": "http://127.0.0.1:1", "timeout": 1.0})
        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is False

    def test_api_sbom(self):
        """SBOM endpoint should return dependency info."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/sbom", json={"project_root": "."})
        assert response.status_code == 200
        data = response.json()
        assert "project_name" in data
