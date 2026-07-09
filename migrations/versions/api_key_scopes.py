"""Add scopes, expires_at, last_used_at to api_keys.

Revision ID: api_key_scopes
Revises: rbac_roles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "api_key_scopes"
down_revision: Union[str, None] = "rbac_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("scopes", sa.Text(), nullable=True, server_default="[]"))
    op.add_column("api_keys", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("api_keys", sa.Column("last_used_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "expires_at")
    op.drop_column("api_keys", "scopes")
