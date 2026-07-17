"""Hybrid search service — combines semantic (pgvector) and keyword (tsvector) search.

Uses Reciprocal Rank Fusion (RRF) to combine results from both search
strategies, producing a re-ranked result set that leverages the strengths
of both dense (semantic) and sparse (keyword) retrieval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# RRF constant — typical k value
RRF_K = 60


def hybrid_search(
    query: str,
    query_embedding: list[float],
    org_id: int | None,
    db: Session,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Execute hybrid semantic + keyword search with RRF.

    Args:
        query: Raw text query for keyword search.
        query_embedding: Vector embedding for semantic search.
        org_id: Organization ID for scoping.
        db: SQLAlchemy session.
        top_k: Number of results to return after fusion.

    Returns:
        List of dicts with chunk_id, content, document_id, and score.
    """
    vector_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Semantic search (pgvector cosine similarity)
    semantic_results: list[dict[str, Any]] = []
    try:
        rows = db.execute(
            text("""
                SELECT dc.id, dc.document_id, dc.content,
                       1 - (dc.embedding <=> :query_vec::vector) AS similarity
                FROM document_chunks dc
                WHERE (dc.organization_id = :org_id OR dc.organization_id IS NULL)
                AND dc.embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT :top_k
            """),
            {"query_vec": vector_str, "org_id": org_id or 0, "top_k": top_k * 2},
        ).fetchall()
        for row in rows:
            semantic_results.append(
                {
                    "id": row[0],
                    "document_id": row[1],
                    "content": row[2],
                    "score": float(row[3] or 0),
                }
            )
    except Exception:
        pass

    # Keyword search (PostgreSQL full-text search via tsvector)
    keyword_results: list[dict[str, Any]] = []
    try:
        tsquery = " & ".join(query.strip().split()[:10])  # First 10 terms
        if tsquery:
            rows = db.execute(
                text("""
                    SELECT dc.id, dc.document_id, dc.content,
                           ts_rank(dc.tsv, to_tsquery('english', :tsquery)) AS relevance
                    FROM document_chunks dc
                    WHERE (dc.organization_id = :org_id OR dc.organization_id IS NULL)
                    AND dc.tsv IS NOT NULL
                    AND dc.tsv @@ to_tsquery('english', :tsquery)
                    ORDER BY relevance DESC
                    LIMIT :top_k
                """),
                {"tsquery": tsquery, "org_id": org_id or 0, "top_k": top_k * 2},
            ).fetchall()
            for row in rows:
                keyword_results.append(
                    {
                        "id": row[0],
                        "document_id": row[1],
                        "content": row[2],
                        "score": float(row[3] or 0),
                    }
                )
    except Exception:
        pass

    # Reciprocal Rank Fusion
    return _rrf_fuse(semantic_results, keyword_results, top_k)


def _rrf_fuse(
    semantic: list[dict[str, Any]],
    keyword: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Apply Reciprocal Rank Fusion to combine two ranked result sets."""
    scores: dict[int, float] = {}

    for rank, item in enumerate(semantic):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    for rank, item in enumerate(keyword):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    # Build merged result set
    seen = set()
    merged = []
    for item in semantic + keyword:
        if item["id"] not in seen:
            seen.add(item["id"])
            item["rrf_score"] = round(scores.get(item["id"], 0.0), 4)
            merged.append(item)

    merged.sort(key=lambda x: x["rrf_score"], reverse=True)
    return merged[:top_k]
