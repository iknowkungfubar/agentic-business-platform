"""Database engine and session management for the TurinTech platform.

Supports PostgreSQL for production, SQLite for development.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings
from app.tenant import TenantSessionFilter

_engine: Any = None
_SessionLocal: Any = None


class Base(DeclarativeBase):
    pass


def _get_engine():
    """Get or create the SQLAlchemy engine lazily."""
    global _engine, _SessionLocal
    if _engine is None:
        url = os.getenv("DATABASE_URL", settings.database_url)
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def reset_engine():
    """Reset the engine singleton (for testing with different DATABASE_URL)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


_tenant_filter = TenantSessionFilter()


def set_tenant_context(org_id: int | None) -> None:
    """Set the tenant context for the current request."""
    _tenant_filter.set_tenant(org_id)


def get_db():
    """Get a database session with tenant context applied."""
    db = _SessionLocal()
    try:
        _tenant_filter.apply(db)
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=_get_engine())


def get_engine():
    return _get_engine()
