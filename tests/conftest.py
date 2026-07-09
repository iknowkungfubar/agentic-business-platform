"""Shared test fixtures for the TurinTech platform."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def test_db(tmp_path: pytest.TempPathFactory) -> Generator[None, None, None]:
    """Isolated temp SQLite DB for each test, with rate limiting disabled.

    Sets DATABASE_URL to a unique temp file, resets the engine, and
    restores the environment on teardown.  Autouse so every test gets
    a clean DB automatically — no need to request it explicitly.
    """
    os.environ["DISABLE_RATE_LIMIT"] = "true"
    old_url = os.environ.get("DATABASE_URL", "")
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import app.db

    app.db.reset_engine()
    app.db.init_db()
    yield
    if old_url:
        os.environ["DATABASE_URL"] = old_url
    else:
        os.environ.pop("DATABASE_URL", None)
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI TestClient pointed at the platform app."""
    from app.api import app

    return TestClient(app)
