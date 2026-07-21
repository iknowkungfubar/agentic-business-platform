"""Add drift_reports table for EU AI Act post-market monitoring.

Revision ID: drift_reports
Revises: prompt_templates
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "drift_reports"
down_revision: str | None = "prompt_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drift_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.Column("model_name", sa.String(255), nullable=True, server_default=""),
        sa.Column("bias_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("hallucination_rate", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("deterministic_proof_json", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("sample_size", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("triggered_alert", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drift_reports_id"), "drift_reports", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_drift_reports_id"), table_name="drift_reports")
    op.drop_table("drift_reports")
