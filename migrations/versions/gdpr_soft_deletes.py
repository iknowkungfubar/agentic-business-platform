"""Add deleted_at columns for GDPR soft deletes.

Revision ID: gdpr_soft_deletes
Revises: white_label_branding
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "gdpr_soft_deletes"
down_revision: Union[str, None] = "white_label_branding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["users", "organizations", "conversations", "documents"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "deleted_at")
