"""Unit tests for the agent evaluation suite."""

from __future__ import annotations


from core.governance.eval import AgentEvalSuite, EvalCriterion


class TestAgentEvalSuite:
    def test_single_criterion_evaluation(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("correctness", weight=1.0))
        result = suite.evaluate(
            "agent-1", "task", "output", scores={"correctness": 0.8}
        )
        assert result.weighted_score == 0.8
        assert result.passed is True  # 0.8 >= 0.7 default threshold

    def test_multi_criteria_weighted_average(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a", weight=0.5))
        suite.add_criterion(EvalCriterion("b", weight=0.5))
        result = suite.evaluate(
            "agent-1", "task", "output", scores={"a": 1.0, "b": 0.0}
        )
        assert result.weighted_score == 0.5

    def test_fails_below_threshold(self):
        suite = AgentEvalSuite(default_threshold=0.7)
        suite.add_criterion(EvalCriterion("correctness", weight=1.0))
        result = suite.evaluate(
            "agent-1", "task", "output", scores={"correctness": 0.3}
        )
        assert result.passed is False

    def test_custom_threshold(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("correctness", weight=1.0))
        result = suite.evaluate(
            "agent-1", "task", "output", scores={"correctness": 0.5}, threshold=0.4
        )
        assert result.passed is True

    def test_missing_score_defaults_to_zero(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a", weight=1.0))
        suite.add_criterion(EvalCriterion("b", weight=1.0))
        result = suite.evaluate("agent-1", "task", "output", scores={"a": 1.0})
        # a: 1.0*1.0 = 1.0, b: 0.0*1.0 = 0.0, total_weight = 2.0, weighted = 0.5
        assert result.weighted_score == 0.5

    def test_history_tracks_evaluations(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a", weight=1.0))
        suite.evaluate("agent-1", "task1", "out1", scores={"a": 0.9})
        suite.evaluate("agent-1", "task2", "out2", scores={"a": 0.5})
        history = suite.get_history()
        assert len(history) == 2

    def test_history_filtered_by_agent(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a", weight=1.0))
        suite.evaluate("agent-1", "t1", "o1", scores={"a": 0.9})
        suite.evaluate("agent-2", "t2", "o2", scores={"a": 0.8})
        assert len(suite.get_history(agent_id="agent-1")) == 1

    def test_get_stats(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a", weight=1.0))
        suite.evaluate("agent-1", "t1", "o1", scores={"a": 0.9})
        suite.evaluate("agent-1", "t2", "o2", scores={"a": 0.3})
        stats = suite.get_stats(agent_id="agent-1")
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["avg_score"] == 0.6

    def test_empty_stats(self):
        suite = AgentEvalSuite()
        stats = suite.get_stats()
        assert stats["total"] == 0

    def test_remove_criterion(self):
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("a"))
        suite.add_criterion(EvalCriterion("b"))
        assert suite.remove_criterion("a") is True
        assert len(suite.criteria) == 1
        assert suite.remove_criterion("nonexistent") is False
