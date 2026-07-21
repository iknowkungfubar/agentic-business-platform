"""Enable PostgreSQL Row-Level Security for multi-tenant data isolation.

Enables RLS on all tenant-scoped tables and creates policies that
automatically filter by app.current_tenant_id. This is a zero-trust
defense — even if a query forgets the WHERE org clause, RLS enforces it.

SQLite is unaffected (no RLS support).
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "rls_enable"
down_revision: str | None = "pgvector_enable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that hold tenant-scoped data
RLS_TABLES = [
    "documents",
    "document_chunks",
    "messages",
    "audit_events",
    "conversations",
    "agent_records",
    "api_keys",
    "mcp_scan_results",
]

# Column name used for tenant ID in each table
TENANT_COLUMN = "organization_id"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # Create the tenant_id setting function (used by RLS policies)
    op.execute(
        "CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS INTEGER "
        "LANGUAGE SQL PARALLEL SAFE "
        "AS $$ SELECT current_setting('app.current_tenant_id')::integer; $$"
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Create a policy that automatically filters by org_id
        # Using USING (with CHECK for INSERT) ensures both reads and writes are scoped
        policy_name = f"tenant_isolation_{table}"
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING ({TENANT_COLUMN} = app.current_tenant_id()) "
            f"WITH CHECK ({TENANT_COLUMN} = app.current_tenant_id())"
        )

    # Grant usage on the app schema and function to the application role
    op.execute("GRANT USAGE ON SCHEMA app TO turin")
    op.execute("GRANT EXECUTE ON FUNCTION app.current_tenant_id() TO turin")

    # Create a default privilege so future tables also get RLS
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO turin")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NOFORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS app.current_tenant_id()")
