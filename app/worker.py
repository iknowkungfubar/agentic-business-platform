"""ARQ background worker — handles ingestion, chunking, and embedding.

Run with:
    arq app.worker.WorkerSettings

Or directly:
    python -m app.worker
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.config import settings as app_settings
from app.worker_settings import worker_settings

# In-memory task status fallback
_task_status: dict[str, dict[str, Any]] = {}

# ── Status Tracking ──────────────────────────────────────────


async def get_task_status(task_id: str) -> dict[str, Any] | None:
    """Get the current status of a background task from Redis."""
    pool = ConnectionPool.from_url(worker_settings.redis_url)
    r = Redis(connection_pool=pool)
    try:
        data = await r.get(f"task:{task_id}")
        if data:
            return json.loads(data)
        return _task_status.get(task_id)
    finally:
        await r.aclose()


async def _set_status(task_id: str, status: str, **kwargs: Any) -> None:
    """Update task status in Redis + local cache."""
    data: dict[str, Any] = {"task_id": task_id, "status": status, "updated_at": datetime.now(UTC).isoformat()}
    data.update(kwargs)
    _task_status[task_id] = data

    pool = ConnectionPool.from_url(worker_settings.redis_url)
    r = Redis(connection_pool=pool)
    try:
        await r.set(f"task:{task_id}", json.dumps(data), ex=86400)
    finally:
        await r.aclose()


def _get_db_session():
    """Create a new DB session for worker use (no FastAPI dependency)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.getenv("DATABASE_URL", app_settings.database_url)
    engine = create_engine(db_url, pool_pre_ping=True)
    session = Session(bind=engine)
    return session, engine


# ── Ingestion Pipeline ────────────────────────────────────────


async def ingest_document(ctx: dict, file_path: str, original_name: str, org_id: int | None) -> dict[str, Any]:
    """Background task: ingest a document, chunk it, generate embeddings, store in DB."""
    task_id = ctx.get("job_id", str(uuid.uuid4()))
    await _set_status(task_id, "processing", file=original_name, progress=0)

    try:
        await _set_status(task_id, "parsing", file=original_name, progress=10)
        from core.pipeline.ingest import DocumentIngester

        ingester = DocumentIngester()
        doc = ingester.ingest(file_path)

        await _set_status(task_id, "chunking", file=original_name, progress=30)
        from core.pipeline.chunk import TextChunker

        chunker = TextChunker(strategy="paragraph")
        dataclass_chunks = chunker.chunk(doc)
        chunk_texts = [c.content for c in dataclass_chunks]

        await _set_status(task_id, "saving", file=original_name, progress=60, total_chunks=len(chunk_texts))

        doc_id = _save_document(doc, original_name, org_id, chunk_texts)

        await _set_status(task_id, "embedding", file=original_name, progress=80)

        # Generate embeddings and update each chunk
        embedded = 0
        session, engine = _get_db_session()
        try:
            from app.models import DocumentChunk

            for chunk in dataclass_chunks:
                embedding = await _generate_embedding(chunk.content)
                if embedding:
                    db_chunk = session.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc_id,
                        DocumentChunk.chunk_index == chunk.index,
                    ).first()
                    if db_chunk:
                        _update_chunk_embedding(session, db_chunk.id, embedding)
                        embedded += 1
            session.commit()
        finally:
            session.close()
            engine.dispose()

        await _set_status(
            task_id, "completed", file=original_name, progress=100,
            document_id=doc_id, chunks=len(chunk_texts), embedded=embedded,
        )
        return {"task_id": task_id, "document_id": doc_id, "status": "completed"}

    except Exception as exc:
        await _set_status(task_id, "failed", file=original_name, error=str(exc))
        raise


def _save_document(doc: Any, original_name: str, org_id: int | None, chunk_texts: list[str]) -> int:
    """Save document + chunks to the database."""
    from app.models import Document as DocModel
    from app.models import DocumentChunk

    session, engine = _get_db_session()
    try:
        record = DocModel(
            source=doc.source,
            content=doc.content,
            file_type=doc.metadata.get("file_type", ""),
            file_name=original_name,
            file_size=doc.metadata.get("file_size", 0),
            organization_id=org_id,
        )
        session.add(record)
        session.flush()

        for i, chunk_text in enumerate(chunk_texts):
            chunk = DocumentChunk(
                document_id=record.id,
                chunk_index=i,
                content=chunk_text,
                token_count=len(chunk_text.split()),
                organization_id=org_id,
            )
            session.add(chunk)

        session.commit()
        return record.id  # type: ignore[return-value]
    finally:
        session.close()
        engine.dispose()


def _update_chunk_embedding(session, chunk_id: int, embedding: list[float]) -> None:
    """Update a chunk's embedding vector using raw pgvector SQL."""
    from sqlalchemy import text

    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
    session.execute(
        text("UPDATE document_chunks SET embedding = :vec::vector WHERE id = :id"),
        {"vec": vector_str, "id": chunk_id},
    )


async def _generate_embedding(text: str) -> list[float] | None:
    """Call the embedding model endpoint to generate a vector."""
    import httpx

    url = f"{worker_settings.inference_url}/embeddings"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={"model": worker_settings.embedding_model, "input": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [{}])[0].get("embedding")
    except Exception:
        return None
    return None


# ── ARQ Worker Configuration ─────────────────────────────────


async def startup(ctx: dict) -> None:
    """ARQ worker startup hook."""
    ctx["redis"] = Redis.from_url(worker_settings.redis_url)
    print(f"[worker] Started — connected to {worker_settings.redis_url}")


async def shutdown(ctx: dict) -> None:
    """ARQ worker shutdown hook."""
    await ctx["redis"].aclose()
    print("[worker] Shutdown complete")


class WorkerSettings:
    """ARQ worker configuration."""
    functions: list = [ingest_document]
    on_startup: Any = startup
    on_shutdown: Any = shutdown
    redis_url: str = worker_settings.redis_url
    max_burst_jobs: int = worker_settings.max_burst_jobs
    job_timeout: int = worker_settings.job_timeout
    poll_delay: float = worker_settings.poll_delay


if __name__ == "__main__":
    import asyncio
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import Worker as ArqWorker

    redis_settings = RedisSettings(
        host=worker_settings.redis_host,
        port=worker_settings.redis_port,
        password=worker_settings.redis_password or None,
        database=0,
    )

    async def main():
        pool = await create_pool(redis_settings)
        worker = ArqWorker(WorkerSettings, pool=pool)
        await worker.async_run()

    asyncio.run(main())
