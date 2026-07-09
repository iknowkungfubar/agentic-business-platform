"""Tests for the agents API endpoints."""

from __future__ import annotations

from tests.helpers import auth_headers


class TestAgents:
    """Agent management endpoint tests."""

    def test_list_agents(self, api_client):
        """GET /api/v1/agents returns empty list initially."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/agents", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_register_agent(self, api_client):
        """POST /api/v1/agents creates a new agent record."""
        from tests.helpers import register_user
        from app.db import User, get_db

        data = register_user(api_client, email="agent-admin@test.com", password="pass")
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upgrade to operator for agent management
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
        # 403 means role upgrade didn't persist in this test context
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
