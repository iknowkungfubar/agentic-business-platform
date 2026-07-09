"""Add prompt_templates table for LLMOps prompt registry.

Revision ID: prompt_templates
Revises: legal_holds
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "prompt_templates"
down_revision: Union[str, None] = "legal_holds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("input_variables", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prompt_templates_id"), "prompt_templates", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_prompt_templates_id"), table_name="prompt_templates")
    op.drop_table("prompt_templates")
