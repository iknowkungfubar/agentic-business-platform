"""Document model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String(20), default="")
    file_name = Column(String(255), default="")
    file_size = Column(Integer, default=0)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
