"""Add under_legal_hold to organizations.

Revision ID: legal_holds
Revises: hitl_workflows
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "legal_holds"
down_revision: str | None = "hitl_workflows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("under_legal_hold", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("organizations", "under_legal_hold")
