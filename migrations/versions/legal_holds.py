"""Add under_legal_hold to organizations.

Revision ID: legal_holds
Revises: hitl_workflows
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "legal_holds"
down_revision: Union[str, None] = "hitl_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("under_legal_hold", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("organizations", "under_legal_hold")
