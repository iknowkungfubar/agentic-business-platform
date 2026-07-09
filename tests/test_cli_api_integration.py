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

    @pytest.fixture(autouse=True)
    def _init_db(self):
        from app.db import init_db
        init_db()

    @pytest.fixture
    def auth_headers(self, _init_db):
        """Register a user and get auth headers."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        r = client.post("/auth/register", json={
            "email": "apitest@test.com", "password": "testpass",
            "full_name": "API Test", "org_name": "APITest",
        })
        # Upgrade to admin
        from app.db import User, get_db
        db = next(get_db())
        user = db.query(User).filter(User.email == "apitest@test.com").first()
        if user:
            user.role = "admin"
            db.commit()

        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

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

    def test_api_classify(self, auth_headers):
        """Classify endpoint should return intent."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/classify", json={"text": "Summarize this report"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "summarization"

    def test_api_route(self, auth_headers):
        """Route endpoint should return model tier."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/route", json={"text": "def foo(): pass"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["model_tier"] == "t3"

    def test_api_evaluate(self, auth_headers):
        """Evaluate endpoint should return policy decision."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        action = {"action_type": "data_access", "resource_type": "cui", "authorized": False}
        response = client.post("/evaluate", json={"action": action}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["effect"] == "deny"

    def test_api_scan_mcp(self, auth_headers):
        """Scan MCP endpoint should handle unreachable servers."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/scan-mcp", json={"url": "http://127.0.0.1:1", "timeout": 1.0}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is False

    def test_api_sbom(self, auth_headers):
        """SBOM endpoint should return dependency info."""
        try:
            from app.api import app
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI not available")

        client = TestClient(app)
        response = client.post("/sbom", json={"project_root": "."}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "project_name" in data
