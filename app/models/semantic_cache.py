"""Semantic cache model — stores LLM responses keyed by query embedding.

Enables retrieval of cached responses when a similar query is detected
(cosine similarity > 0.95), reducing LLM inference costs and latency.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class SemanticCache(Base):
    """Cache entry mapping a query embedding to an LLM response."""

    __tablename__ = "semantic_cache"

    id = Column(Integer, primary_key=True, index=True)
    # Query text (for debugging and display)
    query_text = Column(Text, nullable=False)
    # LLM response stored as text
    response_text = Column(Text, nullable=False)
    # Model tier used for this response
    model_tier = Column(String(20), default="t1")
    # Cosine similarity threshold at insertion time
    similarity_score = Column(Float, default=1.0)
    # Organization scoping
    organization_id = Column(Integer, nullable=True)
    # TTL management
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
