"""E2E wiring tests — verifies the 6 restructured architecture candidates.

This test confirms the architecture restructuring from the previous session
still works end-to-end. It tests:
- Route modules are properly wired
- Service layer is accessible from CLI and API
- Database helpers work through the backward-compat shim
- Rate limiter can be disabled via env var (conftest dependency)

It does NOT test specific business logic (covered by unit tests).
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_app_modules_are_wired() -> None:
    """Verify the restructured api.py picks up all route modules."""
    os.environ["DISABLE_RATE_LIMIT"] = "true"
    import importlib

    import app.api

    importlib.reload(app.api)
    client = TestClient(app.api.app)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.post(
        "/auth/register",
        json={"email": "arch@test.com", "password": "arch123", "org_name": "ArchTest"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()

    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/classify", json={"text": "Hello world"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["intent"] in ("question_answering", "search", "summarization")


def test_service_layer_from_cli() -> None:
    """Verify the service layer is accessible from CLI commands."""
    from app import service

    result = service.classify_text("What is the capital of France?")
    assert result.intent_type is not None

    action = {"action_type": "data_access", "resource_type": "cui", "authorized": False}
    result = service.evaluate_action(action)
    assert result.effect.value == "deny"


def test_db_backward_compat_shim() -> None:
    """Verify app.db shim re-exports everything from app.database + app.models."""
    import app.db

    for name in (
        "User",
        "Organization",
        "APIKey",
        "AgentRecord",
        "AuditEvent",
        "Document",
        "Conversation",
        "Message",
        "Base",
    ):
        assert hasattr(app.db, name), f"app.db missing {name}"
    for name in ("get_db", "init_db", "reset_engine", "get_engine"):
        assert hasattr(app.db, name), f"app.db missing {name}"


def test_conftest_fixtures() -> None:
    """Verify conftest fixtures work for downstream test files."""
    from tests.conftest import api_client, test_db
    from tests.helpers import auth_headers, register_user

    assert callable(test_db)
    assert callable(api_client)
    assert callable(register_user)
    assert callable(auth_headers)


def test_core_init_exports() -> None:
    """Verify core/__init__.py re-exports all public symbols."""
    import core

    for name in (
        "DocumentIngester",
        "IntentClassifier",
        "ModelSelector",
        "PolicyEngine",
        "MCPScanner",
        "SBOMGenerator",
        "Finding",
        "RouteResult",
    ):
        assert hasattr(core, name), f"core missing {name}"


def test_database_helpers() -> None:
    """Verify app.database engine helper functions."""
    from app.database import get_db, get_engine, init_db, reset_engine

    assert callable(reset_engine)
    assert callable(init_db)
    assert callable(get_engine)
    assert callable(get_db)
