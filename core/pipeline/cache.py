"""Semantic cache service — embedding-based LLM response caching.

Uses cosine similarity against stored query embeddings to detect
semantically similar queries and return cached responses.
Threshold: > 0.95 cosine similarity = cache hit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

CACHE_TTL_HOURS = 24
SIMILARITY_THRESHOLD = 0.95


async def get_cached_response(query: str, org_id: int | None, db: Session) -> str | None:
    """Check semantic cache for a similar query.

    Generates an embedding for the query, then searches for existing
    entries with cosine similarity above the threshold.

    Returns the cached response text if found, None otherwise.
    """
    from core.pipeline.embed import generate_embedding

    embedding = await generate_embedding(query)
    if not embedding:
        return None

    # Format vector for pgvector cosine similarity search
    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

    try:
        # Cosine similarity search via pgvector
        result = db.execute(
            text(
                """
                SELECT sc.response_text, 1 - (sc.embedding <=> :query_vec::vector) AS similarity
                FROM semantic_cache sc
                WHERE (sc.organization_id = :org_id OR sc.organization_id IS NULL)
                AND (sc.expires_at IS NULL OR sc.expires_at > :now)
                AND 1 - (sc.embedding <=> :query_vec::vector) > :threshold
                ORDER BY similarity DESC
                LIMIT 1
                """
            ),
            {
                "query_vec": vector_str,
                "org_id": org_id or 0,
                "now": datetime.now(UTC),
                "threshold": SIMILARITY_THRESHOLD,
            },
        ).fetchone()

        if result:
            # Increment access count
            db.execute(
                text("UPDATE semantic_cache SET access_count = access_count + 1 WHERE query_text = :qt"),
                {"qt": result[0][:100]},  # approximate match
            )
            db.commit()
            return str(result[0])

        return None
    except Exception:
        # Fallback: if pgvector is unavailable (e.g. SQLite), no caching
        return None


async def set_cached_response(
    query: str,
    response: str,
    model_tier: str,
    org_id: int | None,
    db: Session,
) -> None:
    """Store a query+response pair in the semantic cache.

    The embedding is generated and stored alongside the response text.
    TTL is 24 hours by default.
    """
    from core.pipeline.embed import generate_embedding

    embedding = await generate_embedding(query)
    if not embedding:
        return

    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
    expires = datetime.now(UTC) + timedelta(hours=CACHE_TTL_HOURS)

    try:
        db.execute(
            text(
                """
                INSERT INTO semantic_cache (query_text, response_text, model_tier, embedding, organization_id, expires_at, created_at)
                VALUES (:query, :response, :tier, :vec::vector, :org_id, :expires, :now)
                """
            ),
            {
                "query": query,
                "response": response,
                "tier": model_tier,
                "vec": vector_str,
                "org_id": org_id,
                "expires": expires,
                "now": datetime.now(UTC),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
