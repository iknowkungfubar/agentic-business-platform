"""Database — backward-compat shim.  Use app.database or app.models directly for new code."""

from __future__ import annotations

from app.database import (
    DATABASE_URL,
    Base,
    get_db,
    get_engine,
    init_db,
    reset_engine,
)
from app.models import (
    AgentRecord,
    APIKey,
    AuditEvent,
    Conversation,
    Document,
    Message,
    Organization,
    User,
)

__all__ = [
    "DATABASE_URL",
    "APIKey",
    "AgentRecord",
    "AuditEvent",
    "Base",
    "Conversation",
    "Document",
    "Message",
    "Organization",
    "User",
    "get_db",
    "get_engine",
    "init_db",
    "reset_engine",
]
