"""Document chunk model with pgvector embedding support.

Each chunk stores a vector embedding that enables cosine similarity
search for RAG (Retrieval-Augmented Generation) in chat queries.
The pgvector extension must be enabled in PostgreSQL.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class DocumentChunk(Base):
    """A chunk of a document with a vector embedding for semantic search."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    # pgvector embedding column (384 dimensions for nomic-embed-text-v1.5)
    # The actual vector column is added via raw SQL in the migration
    # because SQLAlchemy doesn't natively support pgvector.
    # See migrations/versions/ for the enabling migration.
    token_count = Column(Integer, default=0)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
