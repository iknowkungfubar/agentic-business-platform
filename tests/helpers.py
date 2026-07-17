"""Test helpers — reusable utilities for test files."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    email: str = "test@test.com",
    password: str = "testpass123",
    full_name: str = "Test User",
    org_name: str = "TestOrg",
) -> dict[str, Any]:
    """Register a user and return the JSON response."""
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "org_name": org_name,
        },
    ).json()


def auth_headers(
    client: TestClient,
    email: str = "a@test.com",
    password: str = "pass",
) -> dict[str, str]:
    """Register + login, return Bearer auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "org_name": "O"},
    )
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
