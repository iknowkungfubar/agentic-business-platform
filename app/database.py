"""Database engine and session management for the TurinTech platform.

Supports PostgreSQL for production, SQLite for development.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./turin.db")
_engine: Any = None
_SessionLocal: Any = None


class Base(DeclarativeBase):
    pass


def _get_engine():
    """Get or create the SQLAlchemy engine lazily."""
    global _engine, _SessionLocal
    if _engine is None:
        url = os.getenv("DATABASE_URL", "sqlite:///./turin.db")
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def reset_engine():
    """Reset the engine singleton (for testing with different DATABASE_URL)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_db():
    """Get a database session."""
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=_get_engine())


def get_engine():
    return _get_engine()
