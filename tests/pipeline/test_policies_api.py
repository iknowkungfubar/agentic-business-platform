"""Tests for the policies API endpoints."""

from __future__ import annotations

from tests.helpers import auth_headers


class TestPolicies:
    """Policy management endpoint tests."""

    def test_list_policies(self, api_client):
        """GET /api/v1/policies returns available policy templates."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/policies", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "frameworks" in data
        assert "policies" in data
        assert data["total"] > 0

    def test_test_policy(self, api_client):
        """POST /api/v1/test-policy evaluates an action against policies."""
        headers = auth_headers(api_client)
        r = api_client.post(
            "/api/v1/test-policy",
            json={
                "action": {
                    "action_type": "data_access",
                    "resource_type": "cui",
                    "authorized": False,
                }
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert "effect" in r.json()
