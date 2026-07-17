"""Document ingestion endpoint — async dispatch to ARQ worker."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.config import settings
from app.routers import get_current_user
from app.worker import get_task_status

router = APIRouter(tags=["documents"])

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Redis connection for task dispatch
_redis_settings = RedisSettings(
    host="redis",
    port=6379,
    database=0,
)


@router.post("/documents/ingest")
async def ingest_document(
    file: UploadFile,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Upload a document for async ingestion.

    Returns 202 Accepted with a task_id for status polling.
    The background worker will parse, chunk, embed, and store the document.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    allowed_extensions = {".txt", ".md", ".pdf", ".py", ".json", ".yaml", ".yml", ".csv", ".html", ".xml"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(sorted(allowed_extensions))}",
        )

    # Save uploaded file to temp directory
    task_id = str(uuid.uuid4())
    safe_name = f"{task_id}{ext}"
    file_path = UPLOAD_DIR / safe_name

    content = await file.read()
    file_path.write_bytes(content)

    # Dispatch to ARQ worker
    try:
        pool = await create_pool(_redis_settings)
        await pool.enqueue_job(
            "ingest_document",
            str(file_path),
            file.filename,
            user.get("org_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Worker queue unavailable: {exc}")

    return {
        "task_id": task_id,
        "status": "accepted",
        "filename": file.filename,
        "size": len(content),
        "status_url": f"/api/v1/documents/status/{task_id}",
    }


@router.get("/documents/status/{task_id}")
async def document_status(
    task_id: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Poll the status of a document ingestion task."""
    status = await get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status
