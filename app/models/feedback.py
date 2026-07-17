"""LLMFeedback model — stores user preference signals for RLHF fine-tuning.

Each record captures a user's rating (+1 / -1) of an LLM response,
along with optional human corrections for the Model-as-a-Judge pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class LLMFeedback(Base):
    __tablename__ = "llm_feedback"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=False)  # +1 (thumbs up) or -1 (thumbs down)
    human_correction = Column(Text, default="")  # Optional corrected text
    model_tier = Column(String(20), default="")
    prompt_text = Column(Text, default="")  # The prompt that generated this response
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
