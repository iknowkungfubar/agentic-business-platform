"""Add semantic_cache table for LLM response caching.

Revision ID: semantic_cache_add
Revises: rls_enable
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "semantic_cache_add"
down_revision: str | None = "rls_enable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "semantic_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("model_tier", sa.String(20), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_semantic_cache_id"), "semantic_cache", ["id"], unique=False)

    # Add embedding column for pgvector
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TABLE semantic_cache ADD COLUMN embedding vector(384)")
        op.execute(
            "CREATE INDEX ix_semantic_cache_embedding ON semantic_cache "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_semantic_cache_embedding")
    op.drop_index(op.f("ix_semantic_cache_id"), table_name="semantic_cache")
    op.drop_table("semantic_cache")
