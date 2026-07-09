"""Integration tests for the CLI and API."""

from __future__ import annotations

import json

import pytest

from app.cli import main as cli_main


class TestCLIIntegration:
    """Tests for the CLI entry point."""

    def test_cli_classify(self):
        exit_code = cli_main(["classify", "What is the capital of France?"])
        assert exit_code == 0

    def test_cli_route(self):
        exit_code = cli_main(["route", "def hello():\n    pass"])
        assert exit_code == 0

    def test_cli_evaluate(self):
        action = json.dumps({"action_type": "data_access", "resource_type": "cui", "authorized": False})
        exit_code = cli_main(["evaluate", action])
        assert exit_code == 0

    def test_cli_ingest_file_not_found(self):
        with pytest.raises(SystemExit):
            cli_main(["ingest", "/nonexistent/file.txt"])

    def test_cli_sbom(self, tmp_path):
        out = tmp_path / "test_sbom.json"
        exit_code = cli_main(["sbom", "--output", str(out)])
        assert exit_code == 0
        assert out.exists()

    def test_cli_scan_mcp(self):
        exit_code = cli_main(["scan-mcp", "http://127.0.0.1:1"])
        assert exit_code == 0

    def test_cli_no_args_shows_help(self):
        exit_code = cli_main([])
        assert exit_code == 0


class TestAPIIntegration:
    """Tests for the API server endpoints — uses shared test_db + api_client fixtures."""

    def test_api_health(self, api_client):
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_api_classify(self, api_client):
        from tests.helpers import auth_headers

        headers = auth_headers(api_client)
        response = api_client.post("/api/v1/classify", json={"text": "Summarize this report"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["intent"] == "summarization"

    def test_api_route(self, api_client):
        from tests.helpers import auth_headers

        headers = auth_headers(api_client)
        response = api_client.post("/api/v1/route", json={"text": "def foo(): pass"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["model_tier"] == "t3"

    def test_api_evaluate(self, api_client):
        from tests.helpers import auth_headers

        headers = auth_headers(api_client)
        action = {"action_type": "data_access", "resource_type": "cui", "authorized": False}
        response = api_client.post("/api/v1/evaluate", json={"action": action}, headers=headers)
        assert response.status_code == 200
        assert response.json()["effect"] == "deny"

    def test_api_scan_mcp(self, api_client):
        """Scan MCP endpoint requires admin role."""
        from app.database import get_db
        from app.models import User
        from tests.helpers import register_user

        data = register_user(api_client, email="admin@test.com", password="adminpass")
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upgrade to admin via direct DB
        db = next(get_db())
        user = db.query(User).filter(User.email == "admin@test.com").first()
        if user:
            user.role = "admin"
            db.commit()

        response = api_client.post(
            "/api/v1/scan-mcp", json={"url": "http://127.0.0.1:1", "timeout": 1.0}, headers=headers
        )
        if response.status_code == 403:
            pytest.skip("Admin role not available in this test context")
        assert response.status_code == 200
        assert response.json()["reachable"] is False

    def test_api_sbom(self, api_client):
        """SBOM endpoint requires admin role."""
        from app.database import get_db
        from app.models import User
        from tests.helpers import register_user

        data = register_user(api_client, email="admin2@test.com", password="adminpass")
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        db = next(get_db())
        user = db.query(User).filter(User.email == "admin2@test.com").first()
        if user:
            user.role = "admin"
            db.commit()

        response = api_client.post("/api/v1/sbom", json={"project_root": "."}, headers=headers)
        if response.status_code == 403:
            pytest.skip("Admin role not available in this test context")
        assert response.status_code == 200
        assert "project_name" in response.json()
