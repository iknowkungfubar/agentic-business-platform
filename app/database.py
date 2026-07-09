"""Database engine and session management with CQRS read/write splitting.

Supports:
- Single engine (SQLite dev, basic PostgreSQL): set DATABASE_URL
- CQRS (production): set DATABASE_URL_PRIMARY (writes) and DATABASE_URL_REPLICA (reads)
- PgBouncer transaction pooling via optional DATABASE_URL_PGBOUNCER
"""
from __future__ import annotations

import os
from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.tenant import TenantSessionFilter

_write_engine: Any = None
_read_engine: Any = None
_SessionWrite: Any = None
_SessionRead: Any = None


class Base(DeclarativeBase):
    pass


def _get_write_engine():
    """Get or create the write engine (Primary)."""
    global _write_engine, _SessionWrite
    if _write_engine is None:
        url = os.getenv("DATABASE_URL_PRIMARY") or os.getenv("DATABASE_URL", settings.database_url)
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _write_engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _SessionWrite = sessionmaker(autocommit=False, autoflush=False, bind=_write_engine)
    return _write_engine


def _get_read_engine():
    """Get or create the read engine (Replica — falls back to Primary if unset)."""
    global _read_engine, _SessionRead
    if _read_engine is None:
        url = os.getenv("DATABASE_URL_REPLICA") or os.getenv("DATABASE_URL", settings.database_url)
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _read_engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _SessionRead = sessionmaker(autocommit=False, autoflush=False, bind=_read_engine)
    return _read_engine


def reset_engine():
    """Reset both engines (for testing)."""
    global _write_engine, _read_engine, _SessionWrite, _SessionRead
    _write_engine = None
    _read_engine = None
    _SessionWrite = None
    _SessionRead = None


_tenant_filter = TenantSessionFilter()


def set_tenant_context(org_id: int | None) -> None:
    _tenant_filter.set_tenant(org_id)


def get_db() -> Generator[Session, None, None]:
    """Default session (writes). Used by most endpoints — INSERT/UPDATE/DELETE."""
    _get_write_engine()
    db = _SessionWrite()
    try:
        _tenant_filter.apply(db)
        yield db
    finally:
        db.close()


def get_db_read() -> Generator[Session, None, None]:
    """Read-only session (Replica). Use for heavy SELECT queries like Hybrid Search."""
    _get_read_engine()
    db = _SessionRead()
    try:
        _tenant_filter.apply(db)
        yield db
    finally:
        db.close()


def get_db_write() -> Generator[Session, None, None]:
    """Write session (Primary). Use for INSERT/UPDATE/DELETE explicitly."""
    _get_write_engine()
    db = _SessionWrite()
    try:
        _tenant_filter.apply(db)
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on the write engine."""
    Base.metadata.create_all(bind=_get_write_engine())


def get_engine():
    return _get_write_engine()
