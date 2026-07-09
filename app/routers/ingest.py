"""Document ingestion endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import Document as DocumentModel
from app.db import get_db
from app.routers import require_role

router = APIRouter(tags=["documents"])


class IngestResponse(BaseModel):
    id: int
    source: str
    content_length: int
    file_type: str
    file_name: str


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest_document(
    path: str,
    user: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    from core.pipeline.ingest import DocumentIngester  # noqa: PLC0415

    try:
        ingester = DocumentIngester()
        doc = ingester.ingest(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = DocumentModel(
        source=doc.source,
        content=doc.content,
        file_type=doc.metadata.get("file_type", ""),
        file_name=doc.metadata.get("file_name", ""),
        file_size=doc.metadata.get("file_size", 0),
        organization_id=user.get("org_id"),
        created_by=user["user_id"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return IngestResponse(
        id=record.id,
        source=record.source,
        content_length=len(doc.content),
        file_type=record.file_type,
        file_name=record.file_name,
    )
