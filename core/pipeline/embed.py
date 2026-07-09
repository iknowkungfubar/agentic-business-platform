"""Embedding generation service — vector embeddings for RAG.

Calls a local embedding model (e.g., nomic-embed-text-v1.5) via the
configured INFERENCE_URL, using the OpenAI-compatible embeddings API.
"""
from __future__ import annotations

import os
from typing import Any

from app.config import settings


async def generate_embedding(text: str, model: str | None = None) -> list[float] | None:
    """Generate a vector embedding for a text string.

    Args:
        text: The text to embed.
        model: Optional model override (default: nomic-embed-text-v1.5).

    Returns:
        A list of floats representing the embedding vector, or None on failure.
    """
    import httpx  # noqa: PLC0415

    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)
    embed_model = model or "nomic-embed-text-v1.5"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{inference_url}/embeddings",
                json={"model": embed_model, "input": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [{}])[0].get("embedding")
    except Exception:
        return None
    return None


async def generate_embeddings_batch(texts: list[str], model: str | None = None) -> list[list[float] | None]:
    """Generate embeddings for multiple texts in a single batch call.

    Args:
        texts: List of text strings to embed.
        model: Optional model override.

    Returns:
        List of embedding vectors (or None for failed items), same order as input.
    """
    import httpx  # noqa: PLC0415

    inference_url = os.getenv("INFERENCE_URL", settings.inference_url)
    embed_model = model or "nomic-embed-text-v1.5"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
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
    except Exception:
        pass
    return [None] * len(texts)
