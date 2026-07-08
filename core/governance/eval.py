"""Agent evaluation suite — scores agent outputs against defined criteria.

Provides a framework for evaluating agent outputs on dimensions like
correctness, safety, compliance, and cost efficiency. Supports weighted
scoring and generates scorecards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class EvalCriterion:
    """A single evaluation criterion for scoring agent outputs."""

    name: str
    description: str = ""
    weight: float = 1.0


@dataclass
class Scorecard:
    """Evaluation results for a single agent task."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    task: str = ""
    output: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    weighted_score: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    passed: bool = False
    threshold: float = 0.7
    notes: str = ""


class AgentEvalSuite:
    """Evaluates agent outputs against configurable criteria with weighted scoring."""

    def __init__(self, default_threshold: float = 0.7):
        self.criteria: list[EvalCriterion] = []
        self.default_threshold = default_threshold
        self._history: list[Scorecard] = []

    def add_criterion(self, criterion: EvalCriterion) -> None:
        """Add an evaluation criterion."""
        self.criteria.append(criterion)

    def remove_criterion(self, name: str) -> bool:
        """Remove a criterion by name."""
        initial = len(self.criteria)
        self.criteria = [c for c in self.criteria if c.name != name]
        return len(self.criteria) < initial

    def evaluate(
        self,
        agent_id: str,
        task: str,
        output: str,
        scores: dict[str, float] | None = None,
        threshold: float | None = None,
    ) -> Scorecard:
        """Evaluate an agent's output against the configured criteria.

        Args:
            agent_id: Identifier of the agent being evaluated.
            task: The task description the agent was given.
            output: The agent's output to evaluate.
            scores: Dict mapping criterion names to scores (0.0-1.0).
            threshold: Pass/fail threshold for the weighted score.

        Returns:
            Scorecard with evaluation results.

        """
        if scores is None:
            scores = {}

        effective_threshold = threshold if threshold is not None else self.default_threshold

        # Apply criteria: use provided scores or default to 0.0
        full_scores: dict[str, float] = {}
        for criterion in self.criteria:
            full_scores[criterion.name] = scores.get(criterion.name, 0.0)

        # Calculate weighted score
        total_weight = sum(c.weight for c in self.criteria) or 1.0
        weighted = sum(
            full_scores.get(c.name, 0.0) * c.weight
            for c in self.criteria
        ) / total_weight

        scorecard = Scorecard(
            agent_id=agent_id,
            task=task,
            output=output,
            scores=full_scores,
            weighted_score=round(weighted, 4),
            passed=weighted >= effective_threshold,
            threshold=effective_threshold,
        )

        self._history.append(scorecard)
        return scorecard

    def get_history(self, agent_id: str | None = None, limit: int = 50) -> list[Scorecard]:
        """Get evaluation history, optionally filtered by agent."""
        if agent_id:
            filtered = [s for s in self._history if s.agent_id == agent_id]
        else:
            filtered = list(self._history)
        return filtered[-limit:]

    def get_stats(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get evaluation statistics."""
        history = self.get_history(agent_id=agent_id)
        if not history:
            return {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0}

        passed = sum(1 for s in history if s.passed)
        avg_score = sum(s.weighted_score for s in history) / len(history)

        return {
            "total": len(history),
            "passed": passed,
            "failed": len(history) - passed,
            "avg_score": round(avg_score, 4),
        }
