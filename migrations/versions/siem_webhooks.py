"""Add SIEM webhook columns to organizations table.

Revision ID: siem_webhooks
Revises: semantic_cache_add
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "siem_webhooks"
down_revision: str | None = "semantic_cache_add"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("siem_webhook_url", sa.String(512), default="", nullable=True))
    op.add_column("organizations", sa.Column("webhook_secret", sa.String(128), default="", nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "webhook_secret")
    op.drop_column("organizations", "siem_webhook_url")
