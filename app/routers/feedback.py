"""Feedback API — collect RLHF preference signals from users."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LLMFeedback
from app.routers import get_current_user

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int  # +1 or -1
    human_correction: str = ""
    model_tier: str = ""
    prompt_text: str = ""


@router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit user feedback on an LLM response for RLHF collection."""
    if req.rating not in (+1, -1):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Rating must be +1 or -1")

    feedback = LLMFeedback(
        message_id=req.message_id,
        user_id=user.get("user_id", 0),
        rating=req.rating,
        human_correction=req.human_correction,
        model_tier=req.model_tier,
        prompt_text=req.prompt_text[:1024],
    )
    db.add(feedback)
    db.commit()

    return {"status": "recorded", "id": feedback.id, "rating": req.rating}
