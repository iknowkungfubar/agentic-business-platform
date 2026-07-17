"""Shared test fixtures for the TurinTech platform."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def test_db(tmp_path: pytest.TempPathFactory) -> Generator[None, None, None]:
    """Isolated temp SQLite DB for each test, with rate limiting disabled.

    Sets DATABASE_URL to a unique temp file, resets the engine, and
    restores the environment on teardown.  Autouse so every test gets
    a clean DB automatically — no need to request it explicitly.
    """
    os.environ["DISABLE_RATE_LIMIT"] = "true"
    os.environ["DISABLE_MIGRATIONS"] = "true"
    old_url = os.environ.get("DATABASE_URL", "")
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import app.database as app_db

    app_db.reset_engine()
    app_db.init_db()
    yield
    if old_url:
        os.environ["DATABASE_URL"] = old_url
    else:
        os.environ.pop("DATABASE_URL", None)
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI TestClient pointed at the platform app.

    Note: The lifespan runs during TestClient context entry. If you see
    'no such table' errors, ensure test_db sets DATABASE_URL before
    api_client is accessed (it does — test_db is autouse).
    """
    # We import app.api inside the fixture to ensure test_db has already
    # set DATABASE_URL. The lifespan will call _wait_for_db() and
    # _run_migrations(), which should pick up the correct URL.
    #
    # However, alembic's env.py reads DATABASE_URL at env.py runtime,
    # which happens during _run_migrations() -> alembic upgrade head.
    # This is the correct ordering — test_db runs first, then api_client.
    from app.api import app

    return TestClient(app)
