"""Update user role to use RBAC enum values.

Revision ID: rbac_roles
Revises: siem_webhooks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "rbac_roles"
down_revision: Union[str, None] = "siem_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing roles to new enum values
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'"))
        conn.execute(sa.text("UPDATE users SET role = 'user' WHERE role NOT IN ('superadmin', 'org_admin', 'auditor', 'user')"))
        conn.execute(sa.text("UPDATE users SET role = 'org_admin' WHERE role = 'admin'"))
        conn.execute(sa.text("UPDATE users SET role = 'user' WHERE role = 'viewer'"))
    else:
        conn.execute(sa.text("UPDATE users SET role = 'user' WHERE role NOT IN ('superadmin', 'org_admin', 'auditor', 'user')"))
        conn.execute(sa.text("UPDATE users SET role = 'org_admin' WHERE role = 'admin'"))
        conn.execute(sa.text("UPDATE users SET role = 'user' WHERE role = 'viewer'"))


def downgrade() -> None:
    pass
