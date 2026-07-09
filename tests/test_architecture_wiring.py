def test_database_imports() -> None:
    """Verify app.database and app.models exports."""
    from app.database import Base, get_db, init_db, reset_engine, get_engine

    for name in ("User", "Organization", "APIKey", "AgentRecord",
                 "AuditEvent", "Document", "Conversation", "Message"):
        import importlib
        mappings = {"APIKey": "api_key", "AgentRecord": "agent_record",
                     "AuditEvent": "audit_event"}
        mod_name = mappings.get(name, name.lower())
        mod = importlib.import_module(f"app.models.{mod_name}")
        assert hasattr(mod, name), f"app.models missing {name}"
    for fn in (get_db, init_db, reset_engine, get_engine):
        assert callable(fn)
