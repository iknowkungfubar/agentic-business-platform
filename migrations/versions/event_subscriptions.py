"""Add event_subscriptions table for enterprise event bus.

Revision ID: event_subscriptions
Revises: hybrid_search_tsv
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "event_subscriptions"
down_revision: str | None = "hybrid_search_tsv"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("target_url", sa.String(512), nullable=False),
        sa.Column("webhook_secret", sa.String(128), nullable=True, server_default=""),
        sa.Column("is_active", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_subscriptions_id"), "event_subscriptions", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_subscriptions_id"), table_name="event_subscriptions")
    op.drop_table("event_subscriptions")
