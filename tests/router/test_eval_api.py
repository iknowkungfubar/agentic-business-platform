"""Tests for the eval API endpoints."""

from __future__ import annotations

from tests.helpers import auth_headers


def test_eval_criteria(api_client):
    """GET /eval/criteria returns available criteria."""
    headers = auth_headers(api_client)
    r = api_client.get("/eval/criteria", headers=headers)
    assert r.status_code == 200
    assert "criteria" in r.json()


def test_eval_run(api_client):
    """POST /eval/run evaluates an agent output."""
    headers = auth_headers(api_client)
    r = api_client.post(
        "/eval/run",
        json={
            "agent_id": "test-agent",
            "task": "Generate a security report",
            "output": "Report content here",
            "scores": {"correctness": 0.9, "safety": 1.0, "compliance": 0.8},
        },
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "overall_score" in data
    assert "passed" in data
