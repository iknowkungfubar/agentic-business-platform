"""Add HITL columns to workflow_executions.

Revision ID: hitl_workflows
Revises: workflows
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "hitl_workflows"
down_revision: Union[str, None] = "workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_executions", sa.Column("awaiting_approval_from_role", sa.String(50), nullable=True, server_default=""))
    op.add_column("workflow_executions", sa.Column("approval_token", sa.String(64), nullable=True, server_default=""))


def downgrade() -> None:
    op.drop_column("workflow_executions", "approval_token")
    op.drop_column("workflow_executions", "awaiting_approval_from_role")
