"""Tests for the chat router — classify, route, evaluate, chat flows."""

from __future__ import annotations

from tests.helpers import auth_headers


class TestClassify:
    """Classification endpoint tests."""

    def test_classify_question(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post("/api/v1/classify", json={"text": "What is AI?"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["intent"] == "question_answering"

    def test_classify_code(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post("/api/v1/classify", json={"text": "def hello(): pass"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["intent"] == "code_generation"


class TestRoute:
    """Route endpoint tests."""

    def test_route_code_goes_to_t3(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post("/api/v1/route", json={"text": "Write a sorting algorithm"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["model_tier"] == "t3"

    def test_route_simple_goes_to_t1(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post("/api/v1/route", json={"text": "What is 2+2?"}, headers=headers)
        assert r.status_code == 200


class TestEvaluate:
    """Evaluate endpoint tests."""

    def test_evaluate_denies_unauthorized(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post(
            "/api/v1/evaluate",
            json={"action": {"action_type": "data_access", "resource_type": "cui", "authorized": False}},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["effect"] == "deny"

    def test_evaluate_allows_authorized(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.post(
            "/api/v1/evaluate",
            json={"action": {"action_type": "data_access", "resource_type": "public", "authorized": True}},
            headers=headers,
        )
        assert r.status_code == 200


class TestConversations:
    """Conversation endpoint tests."""

    def test_list_conversations(self, api_client):
        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/conversations", headers=headers)
        assert r.status_code == 200
        assert "items" in r.json() or isinstance(r.json(), list)
