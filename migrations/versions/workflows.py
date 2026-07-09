"""Add workflow_executions table for multi-agent DAG orchestration.

Revision ID: workflows
Revises: gdpr_soft_deletes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "workflows"
down_revision: Union[str, None] = "gdpr_soft_deletes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True, server_default=""),
        sa.Column("status", sa.String(50), nullable=True, server_default="PENDING"),
        sa.Column("state_payload", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("current_node", sa.String(100), nullable=True, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_executions_id"), "workflow_executions", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_executions_id"), table_name="workflow_executions")
    op.drop_table("workflow_executions")
