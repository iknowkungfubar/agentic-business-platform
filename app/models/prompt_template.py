"""PromptTemplate model — versioned, organization-scoped system prompts.

Enables non-engineers to tune AI behavior without code deployments.
The active template is queried at inference time, injecting variables
via standard Python string formatting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)  # e.g. "customer_support_v1"
    template_text = Column(Text, nullable=False)
    input_variables = Column(Text, default="[]")  # JSON array of variable names
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
