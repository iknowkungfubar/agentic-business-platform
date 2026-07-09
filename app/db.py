"""Database — backward-compat shim.  Use app.database or app.models directly for new code."""

from app.database import (
    Base,
    get_db,
    get_engine,
    init_db,
    reset_engine,
)
from app.models import (
    APIKey,
    AgentRecord,
    AuditEvent,
    Conversation,
    Document,
    MCPScanResult,
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
