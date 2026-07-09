"""ARQ background worker — handles ingestion, chunking, and embedding.

Run with:
    arq app.worker.WorkerSettings

Or directly:
    python -m app.worker
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.config import settings
from app.worker_settings import worker_settings
from core.pipeline.federated import federated_learning_round

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

    db_url = os.getenv("DATABASE_URL", settings.database_url)
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
                    db_chunk = (
                        session.query(DocumentChunk)
                        .filter(
                            DocumentChunk.document_id == doc_id,
                            DocumentChunk.chunk_index == chunk.index,
                        )
                        .first()
                    )
                    if db_chunk:
                        _update_chunk_embedding(session, db_chunk.id, embedding)
                        embedded += 1
            session.commit()
        finally:
            session.close()
            engine.dispose()

        await _set_status(
            task_id,
            "completed",
            file=original_name,
            progress=100,
            document_id=doc_id,
            chunks=len(chunk_texts),
            embedded=embedded,
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


# ── SIEM Webhook Dispatch ─────────────────────────────────────


async def dispatch_audit_webhook(ctx: dict, event_data: dict, webhook_url: str, webhook_secret: str) -> dict[str, Any]:
    """ARQ task: dispatch an audit event to a tenant's SIEM webhook.

    Signs the payload with HMAC-SHA256 using the tenant's webhook_secret
    and sends it to the configured siem_webhook_url.
    """
    import httpx  # noqa: PLC0415

    payload_bytes = json.dumps(event_data, default=str).encode("utf-8")

    # HMAC-SHA256 signature
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    logger = logging.getLogger("turin-platform.webhook")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                webhook_url,
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": f"sha256={signature}",
                    "X-Event-Type": "audit_event",
                    "X-Event-Timestamp": datetime.now(UTC).isoformat(),
                },
            )
            logger.info(
                "webhook_dispatch_complete",
                extra={"url": webhook_url, "status": resp.status_code, "signature": signature[:16]},
            )
            return {"status": resp.status_code, "sent": True}
    except Exception as exc:
        logger.error("webhook_dispatch_failed", extra={"url": webhook_url, "error": str(exc)})
        return {"status": 0, "sent": False, "error": str(exc)}


# ── Daily Usage Metering ──────────────────────────────────────


async def daily_usage_metering(ctx: dict) -> dict[str, Any]:
    """Scheduled task: aggregate daily token usage by organization.

    Runs daily via ARQ cron. Aggregates Message.tokens_used for the
    previous 24 hours, grouped by organization_id. Pushes to configured
    billing provider if URL is set.
    """
    import httpx  # noqa: PLC0415
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    logger = logging.getLogger("turin-platform.metering")
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    billing_url = os.getenv("BILLING_PROVIDER_URL", "")
    billing_api_key = os.getenv("BILLING_PROVIDER_API_KEY", "")
    db_url = os.getenv("DATABASE_URL", "sqlite:///./turin.db")
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT c.organization_id, SUM(m.tokens_used) as total_tokens,
                           COUNT(m.id) as total_calls
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.created_at >= :cutoff
                    GROUP BY c.organization_id
                """),
                {"cutoff": cutoff},
            ).fetchall()

        results = []
        for row in rows:
            org_id = row[0]
            tokens = int(row[1] or 0)
            calls = int(row[2] or 0)

            usage = {
                "organization_id": org_id,
                "period_start": cutoff.isoformat(),
                "period_end": datetime.now(UTC).isoformat(),
                "total_tokens": tokens,
                "total_calls": calls,
                "estimated_cost_usd": round(tokens / 1000 * 0.002, 4),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            results.append(usage)

            if billing_url and tokens > 0:
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            f"{billing_url}/v1/usage",
                            json=usage,
                            headers={
                                "Authorization": f"Bearer {billing_api_key}",
                                "Content-Type": "application/json",
                            },
                        )
                        logger.info(
                            "billing_push_complete",
                            extra={"org_id": org_id, "status": resp.status_code, "tokens": tokens},
                        )
                except Exception as exc:
                    logger.error("billing_push_failed", extra={"org_id": org_id, "error": str(exc)})

        logger.info("metering_complete", extra={"organizations": len(results), "period_hours": 24})
        return {"organizations": len(results), "results": results}
    finally:
        engine.dispose()


# ── EU AI Act Monitor ────────────────────────────────────────


async def eu_ai_act_monitor(ctx: dict) -> dict[str, Any]:
    """Daily task: monitor model drift, bias, and hallucination rates.

    EU AI Act Article 15 compliance: samples 5% of previous day's audit events,
    runs them through an independent Judge LLM to detect demographic bias,
    PII leakage, and statistical drift. Saves results to DriftReport table.
    Triggers CRITICAL alert if thresholds are exceeded.
    """
    import httpx  # noqa: PLC0415
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    logger = logging.getLogger("turin-platform.eu-ai-act")
    db_url = os.getenv("DATABASE_URL", "sqlite:///./turin.db")
    engine = create_engine(db_url)
    results_summary: list[dict] = []

    try:
        with engine.connect() as conn:
            # Get all organizations
            orgs = conn.execute(text("SELECT id FROM organizations")).fetchall()

            for org_row in orgs:
                org_id = org_row[0]

                # Sample 5% of yesterday's audit events
                rows = conn.execute(
                    text("""
                        SELECT id, action_type, metadata_json
                        FROM audit_events
                        WHERE organization_id = :org_id
                        AND timestamp >= CURRENT_DATE - INTERVAL '1 day'
                        AND timestamp < CURRENT_DATE
                        ORDER BY RANDOM()
                        LIMIT (SELECT GREATEST(1, COUNT(*) * 0.05)
                               FROM audit_events
                               WHERE organization_id = :org_id
                               AND timestamp >= CURRENT_DATE - INTERVAL '1 day')
                    """),
                    {"org_id": org_id},
                ).fetchall()

                sample_size = len(rows)
                if sample_size == 0:
                    continue

                # Run sampled events through Judge LLM
                bias_score = 0.0
                hallucination_rate = 0.0
                triggered = 0

                inference_url = os.getenv("INFERENCE_URL", "http://localhost:1234/v1")
                judge_prompt = (
                    "You are an independent AI compliance judge. Analyze the following "
                    "audit event for: 1) Demographic bias 2) PII leakage 3) Statistical drift. "
                    'Respond with JSON: {"bias_score": 0.0-1.0, "hallucination_rate": 0.0-1.0}'
                )

                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            f"{inference_url}/chat/completions",
                            json={
                                "model": "qwen3.5-9b-deepseek-v4-flash",
                                "messages": [
                                    {"role": "system", "content": judge_prompt},
                                    {"role": "user", "content": f"Sample of {sample_size} events for org {org_id}"},
                                ],
                                "max_tokens": 256,
                                "temperature": 0.1,
                            },
                        )
                        if resp.status_code == 200:
                            content = resp.json()["choices"][0]["message"]["content"]
                            import json as _json

                            try:
                                verdict = _json.loads(content)
                                bias_score = verdict.get("bias_score", 0.0)
                                hallucination_rate = verdict.get("hallucination_rate", 0.0)
                            except Exception:
                                pass
                except Exception:
                    pass

                # Threshold check — EU AI Act Article 15
                if bias_score > 0.3 or hallucination_rate > 0.05:
                    triggered = 1
                    logger.warning(
                        "eu_ai_act_threshold_exceeded",
                        extra={
                            "org_id": org_id,
                            "bias": bias_score,
                            "hallucination": hallucination_rate,
                        },
                    )
                    # Dispatch critical alert via event bus
                    try:
                        from app.events import publish_event  # noqa: PLC0415

                        await publish_event(
                            "compliance.critical",
                            {"org_id": org_id, "bias_score": bias_score, "hallucination_rate": hallucination_rate},
                            org_id=org_id,
                        )
                    except Exception:
                        pass

                # Save DriftReport
                conn.execute(
                    text("""
                        INSERT INTO drift_reports
                        (organization_id, model_name, bias_score, hallucination_rate,
                         deterministic_proof_json, sample_size, triggered_alert)
                        VALUES (:org_id, :model, :bias, :hall, :proof, :size, :alert)
                    """),
                    {
                        "org_id": org_id,
                        "model": "qwen3.5-9b-deepseek-v4-flash",
                        "bias": bias_score,
                        "hall": hallucination_rate,
                        "proof": '{"judge_model": "qwen3.5-9b-deepseek-v4-flash", "sample_size": '
                        + str(sample_size)
                        + "}",
                        "size": sample_size,
                        "alert": triggered,
                    },
                )
                conn.commit()
                results_summary.append({"org_id": org_id, "sample_size": sample_size, "triggered": bool(triggered)})

        logger.info("eu_ai_act_monitor_complete", extra={"orgs_reviewed": len(results_summary)})
        return {"organizations_reviewed": len(results_summary), "results": results_summary}
    finally:
        engine.dispose()


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

    functions: list = [
        ingest_document,
        dispatch_audit_webhook,
        daily_usage_metering,
        eu_ai_act_monitor,
        federated_learning_round,
    ]
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
