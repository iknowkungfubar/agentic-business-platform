"""Add HITL columns to workflow_executions.

Revision ID: hitl_workflows
Revises: workflows
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "hitl_workflows"
down_revision: str | None = "workflows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_executions", sa.Column("awaiting_approval_from_role", sa.String(50), nullable=True, server_default=""))
    op.add_column("workflow_executions", sa.Column("approval_token", sa.String(64), nullable=True, server_default=""))


def downgrade() -> None:
    op.drop_column("workflow_executions", "approval_token")
    op.drop_column("workflow_executions", "awaiting_approval_from_role")
