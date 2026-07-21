"""Add scopes, expires_at, last_used_at to api_keys.

Revision ID: api_key_scopes
Revises: rbac_roles
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "api_key_scopes"
down_revision: str | None = "rbac_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("scopes", sa.Text(), nullable=True, server_default="[]"))
    op.add_column("api_keys", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("api_keys", sa.Column("last_used_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "expires_at")
    op.drop_column("api_keys", "scopes")
