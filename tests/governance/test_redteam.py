"""Unit tests for the red-team scheduler."""

from __future__ import annotations

import pytest

from core.governance.redteam import RedTeamScheduler


class TestRedTeamScheduler:
    def test_schedule_test(self):
        scheduler = RedTeamScheduler()
        test = scheduler.schedule(
            "agent-1", "prompt_injection", "Test agent for prompt injection"
        )
        assert test.agent_id == "agent-1"
        assert test.test_type == "prompt_injection"
        assert test.status == "scheduled"
        assert test.passed is None

    def test_complete_test_passed(self):
        scheduler = RedTeamScheduler()
        test = scheduler.schedule("agent-1", "test", "")
        result = scheduler.complete_test(
            test.id, passed=True, findings=["All checks passed"]
        )
        assert result.status == "completed"
        assert result.passed is True
        assert result.completed_at is not None

    def test_complete_test_failed(self):
        scheduler = RedTeamScheduler()
        test = scheduler.schedule("agent-1", "test", "")
        result = scheduler.complete_test(
            test.id, passed=False, findings=["Vulnerability found"]
        )
        assert result.status == "completed"
        assert result.passed is False

    def test_complete_nonexistent_test_raises(self):
        scheduler = RedTeamScheduler()
        with pytest.raises(KeyError):
            scheduler.complete_test("nonexistent", passed=True)

    def test_cancel_test(self):
        scheduler = RedTeamScheduler()
        test = scheduler.schedule("agent-1", "test", "")
        result = scheduler.cancel_test(test.id)
        assert result.status == "cancelled"

    def test_get_history_by_agent(self):
        scheduler = RedTeamScheduler()
        t1 = scheduler.schedule("agent-1", "a", "")
        t2 = scheduler.schedule("agent-1", "b", "")
        scheduler.schedule("agent-2", "c", "")
        scheduler.complete_test(t1.id, passed=True)
        scheduler.complete_test(t2.id, passed=False)
        history = scheduler.get_history(agent_id="agent-1")
        assert len(history) == 2

    def test_get_history_by_status(self):
        scheduler = RedTeamScheduler()
        t1 = scheduler.schedule("agent-1", "a", "")
        scheduler.schedule("agent-1", "b", "")
        scheduler.complete_test(t1.id, passed=True)
        completed = scheduler.get_history(status="completed")
        scheduled = scheduler.get_history(status="scheduled")
        assert len(completed) == 1
        assert len(scheduled) == 1

    def test_get_stats(self):
        scheduler = RedTeamScheduler()
        t1 = scheduler.schedule("agent-1", "a", "")
        t2 = scheduler.schedule("agent-1", "b", "")
        t3 = scheduler.schedule("agent-1", "c", "")
        scheduler.complete_test(t1.id, passed=True)
        scheduler.complete_test(t2.id, passed=True)
        scheduler.complete_test(t3.id, passed=False)
        stats = scheduler.get_stats(agent_id="agent-1")
        assert stats["total"] == 3
        assert stats["completed"] == 3
        assert stats["passed"] == 2
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 0.6667

    def test_empty_stats(self):
        scheduler = RedTeamScheduler()
        stats = scheduler.get_stats()
        assert stats["total"] == 0

    def test_get_test_by_id(self):
        scheduler = RedTeamScheduler()
        test = scheduler.schedule("agent-1", "test", "")
        retrieved = scheduler.get_test(test.id)
        assert retrieved is not None
        assert retrieved.id == test.id
        assert scheduler.get_test("nonexistent") is None

    def test_get_stats_with_no_completed_tests(self):
        scheduler = RedTeamScheduler()
        scheduler.schedule("agent-1", "test", "")
        stats = scheduler.get_stats(agent_id="agent-1")
        assert stats["completed"] == 0
        assert stats["pass_rate"] == 0.0
