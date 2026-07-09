"""Agent evaluation endpoints — evaluate agent outputs, list criteria, get stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers import get_current_user

router = APIRouter(prefix="/eval", tags=["eval"])


class EvalRunRequest(BaseModel):
    agent_id: str = "test-agent"
    task: str = "Test task"
    output: str = "Test output"
    scores: dict[str, float] = {}


@router.post("/run")
async def run_eval(req: EvalRunRequest, user: dict = Depends(get_current_user)):
    """Evaluate an agent output against default criteria and return results."""
    from core.governance.eval import AgentEvalSuite, EvalCriterion  # noqa: PLC0415

    suite = AgentEvalSuite()
    suite.add_criterion(EvalCriterion("correctness", weight=0.4))
    suite.add_criterion(EvalCriterion("safety", weight=0.3))
    suite.add_criterion(EvalCriterion("compliance", weight=0.3))

    scores = req.scores or {}
    scorecard = suite.evaluate(
        agent_id=req.agent_id,
        task=req.task,
        output=req.output,
        scores=scores,
    )

    return {
        "result_id": scorecard.id,
        "agent_id": scorecard.agent_id,
        "overall_score": scorecard.weighted_score,
        "threshold": scorecard.threshold,
        "passed": scorecard.passed,
        "scores": scorecard.scores,
    }


@router.get("/results/{result_id}")
async def get_eval_result(
    result_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific evaluation result by ID.

    Note: Eval results are in-memory and only available for the current
    process lifetime. Persistent storage requires database integration.
    """
    from core.governance.eval import AgentEvalSuite  # noqa: PLC0415

    suite = AgentEvalSuite()
    history = suite.get_history(limit=1000)
    for s in history:
        if s.id == result_id:
            return {
                "id": s.id,
                "agent_id": s.agent_id,
                "task": s.task,
                "overall_score": s.weighted_score,
                "passed": s.passed,
                "scores": s.scores,
                "evaluated_at": s.evaluated_at.isoformat() if s.evaluated_at else None,
            }
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Evaluation result not found (in-memory results may have expired)")


@router.get("/criteria")
async def list_criteria(user: dict = Depends(get_current_user)):
    """List available evaluation criteria with descriptions."""
    from core.governance.eval import EvalCriterion  # noqa: PLC0415

    return {
        "criteria": [
            {"name": "correctness", "description": "Output correctness against expected result", "default_weight": 0.4},
            {"name": "safety", "description": "Output safety — no harmful content", "default_weight": 0.3},
            {"name": "compliance", "description": "Policy compliance", "default_weight": 0.3},
        ]
    }


@router.post("/history")
async def eval_history(
    agent_id: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get evaluation history (note: in-memory, resets on restart)."""
    from core.governance.eval import AgentEvalSuite  # noqa: PLC0415

    suite = AgentEvalSuite()
    history = suite.get_history(agent_id=agent_id, limit=limit)
    return {
        "total": len(history),
        "history": [
            {
                "agent_id": s.agent_id,
                "task": s.task[:100],
                "score": s.weighted_score,
                "passed": s.passed,
                "timestamp": s.evaluated_at.isoformat() if s.evaluated_at else None,
            }
            for s in history
        ],
    }
