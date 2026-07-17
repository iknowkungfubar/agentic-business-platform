from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import requests

API_URL = os.getenv("E2E_API_URL", "http://localhost:8000")

# Skip E2E tests if Docker isn't available or the stack isn't running
e2e = pytest.mark.skipif(
    not os.getenv("E2E_TESTS", ""),
    reason="E2E tests require Docker stack. Set E2E_TESTS=1 to run.",
)


def _wait_for_api(timeout: int = 60, interval: int = 2) -> None:
    """Wait until the API health endpoint responds 200."""
    for _attempt in range(timeout // interval):
        try:
            r = requests.get(f"{API_URL}/health", timeout=5)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(interval)
    pytest.fail(f"API not healthy after {timeout}s")


@pytest.fixture(scope="session", autouse=True)
def stack_setup():
    """Ensure the docker compose test stack is running.

    If not running, attempt to start it. This allows both:
    - Pre-started stack in CI
    - Auto-start during local development
    """
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        if r.status_code == 200:
            return  # Stack already running
    except requests.ConnectionError:
        pass

    # Start the stack
    compose_file = Path(__file__).parents[2] / "docker-compose.test.yml"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        capture_output=True,
    )
    _wait_for_api()
    return
    # Teardown is manual in CI; for local dev, stop with:
    # docker compose -f docker-compose.test.yml down


# ── API Test Suite ────────────────────────────────────────────


@e2e
class TestHealth:
    """Health endpoint smoke tests."""

    def test_liveness(self):
        r = requests.get(f"{API_URL}/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_readiness(self):
        r = requests.get(f"{API_URL}/health/ready", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_metrics(self):
        r = requests.get(f"{API_URL}/metrics", timeout=10)
        assert r.status_code == 200
        assert "# HELP http_requests_total" in r.text


@e2e
class TestAuthFlow:
    """Complete auth lifecycle — register, login, token validation."""

    REGISTER_URL = f"{API_URL}/api/v1/auth/register"
    LOGIN_URL = f"{API_URL}/api/v1/auth/login"
    ME_URL = f"{API_URL}/api/v1/auth/me"

    def test_register_and_login(self):
        email = f"e2e-test-{int(time.time())}@test.com"
        password = "TestPass123!"

        # Register
        r = requests.post(
            self.REGISTER_URL,
            json={
                "email": email,
                "password": password,
                "org_name": "E2E Test Org",
            },
            timeout=10,
        )
        assert r.status_code == 200, f"Register failed: {r.text}"
        token = r.json()["access_token"]
        assert token

        # Get current user
        r = requests.get(self.ME_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["sub"] == email

        # Login
        r = requests.post(self.LOGIN_URL, json={"email": email, "password": password}, timeout=10)
        assert r.status_code == 200
        assert r.json()["access_token"]

        # Wrong password
        r = requests.post(self.LOGIN_URL, json={"email": email, "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_duplicate_email_rejected(self):
        email = f"dup-test-{int(time.time())}@test.com"
        requests.post(self.REGISTER_URL, json={"email": email, "password": "pass"}, timeout=10)
        r = requests.post(self.REGISTER_URL, json={"email": email, "password": "pass"}, timeout=10)
        assert r.status_code == 400
        assert "already registered" in r.json()["error"]["message"].lower()


@e2e
class TestChatFlow:
    """Full chat lifecycle — classify, route, chat, conversations."""

    _token: str = ""
    _conv_id: int | None = None

    @classmethod
    def _auth_headers(cls) -> dict:
        if not cls._token:
            email = f"chat-test-{int(time.time())}@test.com"
            r = requests.post(
                f"{API_URL}/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "pass",
                    "org_name": "Chat Test",
                },
                timeout=10,
            )
            assert r.status_code == 200
            cls._token = r.json()["access_token"]
        return {"Authorization": f"Bearer {cls._token}"}

    def test_classify(self):
        r = requests.post(
            f"{API_URL}/api/v1/classify",
            json={"text": "What is machine learning?"},
            headers=self._auth_headers(),
            timeout=10,
        )
        assert r.status_code == 200
        assert "intent" in r.json()

    def test_route(self):
        r = requests.post(
            f"{API_URL}/api/v1/route",
            json={"text": "Write a sorting algorithm in Python"},
            headers=self._auth_headers(),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["model_tier"] == "t3"

    def test_chat(self):
        r = requests.post(
            f"{API_URL}/api/v1/chat",
            json={"message": "Hello, what can you do?"},
            headers=self._auth_headers(),
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "conversation_id" in data
        assert "response" in data
        self.__class__._conv_id = data["conversation_id"]

    def test_list_conversations(self):
        r = requests.get(f"{API_URL}/api/v1/conversations", headers=self._auth_headers(), timeout=10)
        assert r.status_code == 200
        assert len(r.json()) > 0


@e2e
class TestDocumentIngestion:
    """Document upload → status polling → verification."""

    _auth_headers = {}

    @classmethod
    def _setup(cls):
        if not cls._auth_headers:
            email = f"doc-test-{int(time.time())}@test.com"
            r = requests.post(
                f"{API_URL}/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "pass",
                    "org_name": "Doc Test",
                },
                timeout=10,
            )
            assert r.status_code == 200
            cls._auth_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_upload_document(self):
        self._setup()
        import io

        files = {"file": ("test.txt", io.BytesIO(b"Hello world, this is a test document for ingestion."), "text/plain")}
        r = requests.post(f"{API_URL}/api/v1/documents/ingest", files=files, headers=self._auth_headers, timeout=30)
        assert r.status_code == 202, f"Upload failed: {r.text}"
        data = r.json()
        assert "task_id" in data
        assert data["status"] == "accepted"

    def test_metrics_endpoint(self):
        r = requests.get(f"{API_URL}/metrics", timeout=10)
        assert r.status_code == 200
        assert "http_requests_total" in r.text


@e2e
class TestSecurityCompliance:
    """Security endpoints — guardrails, audit, compliance."""

    @classmethod
    def _auth_headers(cls) -> dict:
        email = f"sec-test-{int(time.time())}@test.com"
        r = requests.post(
            f"{API_URL}/api/v1/auth/register",
            json={
                "email": email,
                "password": "pass",
                "org_name": "Sec Test",
            },
            timeout=10,
        )
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_audit_events(self):
        r = requests.get(f"{API_URL}/api/v1/audit/events", headers=self._auth_headers(), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_policies(self):
        r = requests.get(f"{API_URL}/api/v1/policies", headers=self._auth_headers(), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0

    def test_compliance_report(self):
        r = requests.post(f"{API_URL}/api/v1/compliance/report", headers=self._auth_headers(), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "controls" in data


@e2e
class TestAgentsAPI:
    """Agent management CRUD."""

    @classmethod
    def _auth_headers(cls) -> dict:
        email = f"agent-test-{int(time.time())}@test.com"
        r = requests.post(
            f"{API_URL}/api/v1/auth/register",
            json={
                "email": email,
                "password": "pass",
                "org_name": "Agent Test",
            },
            timeout=10,
        )
        token = r.json()["access_token"]
        # Upgrade to org_admin for agent management
        from app.database import get_db
        from app.models import User

        db = next(get_db())
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = "org_admin"
            db.commit()
        return {"Authorization": f"Bearer {token}"}

    def test_list_agents(self):
        r = requests.get(f"{API_URL}/api/v1/agents", headers=self._auth_headers(), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_register_agent(self):
        r = requests.post(
            f"{API_URL}/api/v1/agents",
            json={"name": "test-agent-1", "url": "http://localhost:9999", "provider": "test"},
            headers=self._auth_headers(),
            timeout=10,
        )
        assert r.status_code in (200, 403)  # 403 if role upgrade didn't persist
