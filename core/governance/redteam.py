"""Red-team scheduler — schedule and track adversarial testing against agents.

Supports scheduling recurring red-team tests, recording results, and
tracking pass/fail statistics over time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class RedTeamTest:
    """A single red-team test against an agent."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    test_type: str = ""
    description: str = ""
    status: str = "scheduled"  # scheduled, in_progress, completed, cancelled
    passed: bool | None = None
    findings: list[str] = field(default_factory=list)
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class RedTeamScheduler:
    """Manages red-team test scheduling, execution, and results tracking."""

    def __init__(self):
        self._tests: dict[str, RedTeamTest] = {}

    def schedule(
        self,
        agent_id: str,
        test_type: str,
        description: str = "",
    ) -> RedTeamTest:
        """Schedule a new red-team test.

        Args:
            agent_id: The agent to test.
            test_type: Type of test (prompt_injection, data_extraction, etc.).
            description: Description of the test scope.

        Returns:
            The scheduled RedTeamTest.

        """
        test = RedTeamTest(
            agent_id=agent_id,
            test_type=test_type,
            description=description,
        )
        self._tests[test.id] = test
        return test

    def complete_test(
        self,
        test_id: str,
        passed: bool,
        findings: list[str] | None = None,
    ) -> RedTeamTest:
        """Record the results of a red-team test.

        Args:
            test_id: The test ID to complete.
            passed: Whether the agent passed the test.
            findings: List of findings or observations.

        Returns:
            The updated RedTeamTest.

        Raises:
            KeyError: If the test_id doesn't exist.

        """
        if test_id not in self._tests:
            raise KeyError(f"Test not found: {test_id}")

        test = self._tests[test_id]
        test.status = "completed"
        test.passed = passed
        test.findings = findings or []
        test.completed_at = datetime.now(UTC)
        return test

    def cancel_test(self, test_id: str) -> RedTeamTest:
        """Cancel a scheduled test."""
        if test_id not in self._tests:
            raise KeyError(f"Test not found: {test_id}")

        test = self._tests[test_id]
        test.status = "cancelled"
        return test

    def get_test(self, test_id: str) -> RedTeamTest | None:
        """Get a specific test by ID."""
        return self._tests.get(test_id)

    def get_history(
        self,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[RedTeamTest]:
        """Get test history with optional filters."""
        tests = list(self._tests.values())

        if agent_id:
            tests = [t for t in tests if t.agent_id == agent_id]
        if status:
            tests = [t for t in tests if t.status == status]

        tests.sort(key=lambda t: t.scheduled_at, reverse=True)
        return tests[:limit]

    def get_stats(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get red-team testing statistics."""
        completed = self.get_history(agent_id=agent_id, status="completed")
        scheduled = self.get_history(agent_id=agent_id, status="scheduled")

        if not completed:
            return {
                "total": len(scheduled),
                "completed": 0,
                "scheduled": len(scheduled),
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
            }

        passed = sum(1 for t in completed if t.passed)
        failed = len(completed) - passed

        return {
            "total": len(scheduled) + len(completed),
            "completed": len(completed),
            "scheduled": len(scheduled),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(completed), 4) if completed else 0.0,
        }
