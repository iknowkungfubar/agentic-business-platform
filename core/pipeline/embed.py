"""Embedding generation service — vector embeddings for RAG with retry logic.

Calls a local embedding model (e.g., nomic-embed-text-v1.5) via the
configured INFERENCE_URL, using the OpenAI-compatible embeddings API.

Includes:
- Tenacity retry with exponential backoff + jitter
- Hard timeout per attempt (10s)
- Graceful fallback returning None on failure instead of raising
"""

from __future__ import annotations

import logging
import os

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.retry import retry_if_exception_type

from app.config import settings

logger = logging.getLogger("turin-platform.embedding")

# Exceptions that warrant a retry (transient)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential_jitter(initial=1, max=10, jitter=2),
    "retry": retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    "after": after_log(logger, logging.WARNING),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": False,
}


@retry(**RETRY_CONFIG)
async def generate_embedding(text: str, model: str | None = None) -> list[float] | None:
    """Generate a vector embedding for a text string with retry logic.

    Retries up to 3 times with exponential backoff + jitter on transient
    failures. Returns None if all retries are exhausted (graceful fallback).
    """
    import httpx

    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)
    embed_model = model or "nomic-embed-text-v1.5"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{inference_url}/embeddings",
                json={"model": embed_model, "input": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [{}])[0].get("embedding")
            logger.warning("embedding_api_error", extra={"status": resp.status_code, "model": embed_model})
            return None
    except RETRYABLE_EXCEPTIONS:
        logger.exception("embedding_retries_exhausted", extra={"model": embed_model})
        return None


@retry(**RETRY_CONFIG)
async def generate_embeddings_batch(texts: list[str], model: str | None = None) -> list[list[float] | None]:
    """Generate embeddings for multiple texts with retry logic."""
    import httpx

    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)
    embed_model = model or "nomic-embed-text-v1.5"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{inference_url}/embeddings",
                json={"model": embed_model, "input": texts},
            )
            if resp.status_code == 200:
                data = resp.json()
                results: list[list[float] | None] = [None] * len(texts)
                for item in data.get("data", []):
                    idx = item.get("index")
                    if idx is not None and idx < len(results):
                        results[idx] = item.get("embedding")
                return results
    except RETRYABLE_EXCEPTIONS:
        logger.exception("embedding_batch_retries_exhausted", extra={"model": embed_model, "count": len(texts)})

    return [None] * len(texts)
