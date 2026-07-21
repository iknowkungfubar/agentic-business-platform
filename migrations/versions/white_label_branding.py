"""Add white-label branding columns to organizations table.

Revision ID: white_label_branding
Revises: event_subscriptions
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "white_label_branding"
down_revision: str | None = "event_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("custom_domain", sa.String(255), default="", nullable=True))
    op.add_column("organizations", sa.Column("logo_url", sa.String(512), default="", nullable=True))
    op.add_column("organizations", sa.Column("primary_color_hex", sa.String(7), default="#10b981", nullable=True))
    op.add_column("organizations", sa.Column("secondary_color_hex", sa.String(7), default="#6366f1", nullable=True))
    op.create_index(op.f("ix_organizations_custom_domain"), "organizations", ["custom_domain"])


def downgrade() -> None:
    op.drop_index(op.f("ix_organizations_custom_domain"), table_name="organizations")
    op.drop_column("organizations", "secondary_color_hex")
    op.drop_column("organizations", "primary_color_hex")
    op.drop_column("organizations", "logo_url")
    op.drop_column("organizations", "custom_domain")
