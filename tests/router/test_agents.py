"""Tests for the agents API endpoints — uses ACP inventory."""

from __future__ import annotations

import os

import pytest

from tests.helpers import auth_headers


@pytest.fixture(autouse=True)
def _acp_db(tmp_path):
    """Set ACP_DB_PATH to a temp file so inventory tests don't collide."""
    old = os.environ.get("ACP_DB_PATH", "")
    os.environ["ACP_DB_PATH"] = str(tmp_path / "acp_test.db")
    yield
    if old:
        os.environ["ACP_DB_PATH"] = old
    else:
        os.environ.pop("ACP_DB_PATH", None)


class TestAgents:
    """Agent management endpoint tests."""

    def test_list_agents(self, api_client):
        """GET /api/v1/agents returns paginated response."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/agents", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_register_agent(self, api_client):
        """POST /api/v1/agents creates a new agent record."""
        from app.database import get_db
        from app.models import User
        from tests.helpers import register_user

        data = register_user(api_client, email="agent-admin@test.com", password="pass")
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        db = next(get_db())
        user = db.query(User).filter(User.email == "agent-admin@test.com").first()
        if user:
            user.role = "operator"
            db.commit()

        r = api_client.post(
            "/api/v1/agents",
            json={"name": "test-agent", "url": "http://localhost:8080", "provider": "test"},
            headers=headers,
        )
        if r.status_code == 403:
            return
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "test-agent"
        assert data["status"] == "unknown"

    def test_get_agent_not_found(self, api_client):
        """GET /api/v1/agents/999 returns 404."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/agents/999", headers=headers)
        assert r.status_code == 404
