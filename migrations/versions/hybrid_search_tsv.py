"""Add tsvector column to document_chunks for hybrid search support.

Revision ID: hybrid_search_tsv
Revises: api_key_scopes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "hybrid_search_tsv"
down_revision: Union[str, None] = "api_key_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TABLE document_chunks ADD COLUMN tsv tsvector")
        op.execute(
            "CREATE INDEX ix_document_chunks_tsv ON document_chunks USING gin(tsv)"
        )
        # Trigger to auto-update tsvector on content change
        op.execute("""
            CREATE OR REPLACE FUNCTION document_chunks_tsv_update() RETURNS trigger AS $$
            BEGIN
                NEW.tsv := to_tsvector('english', COALESCE(NEW.content, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER trg_document_chunks_tsv
            BEFORE INSERT OR UPDATE ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION document_chunks_tsv_update()
        """)
        # Backfill existing rows
        op.execute("UPDATE document_chunks SET tsv = to_tsvector('english', COALESCE(content, ''))")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_tsv ON document_chunks")
        op.execute("DROP FUNCTION IF EXISTS document_chunks_tsv_update")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_tsv")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tsv")
