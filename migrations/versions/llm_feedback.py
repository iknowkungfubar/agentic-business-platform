"""Add llm_feedback table for RLHF preference signals.

Revision ID: llm_feedback
Revises: prompt_templates
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "llm_feedback"
down_revision: str | None = "prompt_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("human_correction", sa.Text(), nullable=True, server_default=""),
        sa.Column("model_tier", sa.String(20), nullable=True, server_default=""),
        sa.Column("prompt_text", sa.Text(), nullable=True, server_default=""),
        sa.Column("metadata_json", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_feedback_id"), "llm_feedback", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_feedback_id"), table_name="llm_feedback")
    op.drop_table("llm_feedback")
