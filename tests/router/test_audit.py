"""Tests for the audit events API endpoints."""

from __future__ import annotations

from tests.helpers import auth_headers


class TestAudit:
    """Audit event API endpoint tests."""

    def test_list_audit_events(self, api_client):
        """GET /api/v1/audit/events returns paginated results."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/audit/events", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_audit_event_not_found(self, api_client):
        """GET /api/v1/audit/events/999 returns 404."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/audit/events/999", headers=headers)
        assert r.status_code == 404

    def test_audit_integrity(self, api_client):
        """GET /api/v1/audit/integrity returns chain verification status."""
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/audit/integrity", headers=headers)
        assert r.status_code == 200
        assert "total_events" in r.json()
