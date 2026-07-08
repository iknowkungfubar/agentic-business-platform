"""Policy engine — rule-based evaluation of agent actions against defined policies.

Evaluates agent actions (tool calls, data access, model selection) against
a set of PolicyRules and returns an allow/deny/audit result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuleEffect(str, Enum):
    """The effect of a policy rule when its conditions match."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"


@dataclass
class PolicyRule:
    """A single policy rule that evaluates agent actions."""

    name: str
    description: str = ""
    effect: RuleEffect = RuleEffect.DENY
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class EvaluationResult:
    """Result of evaluating an action against the policy engine."""

    effect: RuleEffect
    matched_rule: str = ""
    matched_rules: list[str] = field(default_factory=list)
    details: str = ""


class PolicyEngine:
    """Evaluates agent actions against a set of policy rules.

    Rules are evaluated in priority order (highest first). The first
    matching rule determines the result. DENY takes precedence over
    ALLOW when priorities are equal.
    """

    def __init__(self):
        self._rules: list[PolicyRule] = []

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule to the engine."""
        self._rules.append(rule)
        # Sort by priority descending — highest priority first
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rules(self, rules: list[PolicyRule]) -> None:
        """Add multiple rules at once."""
        for rule in rules:
            self.add_rule(rule)

    def evaluate(self, action: dict[str, Any]) -> EvaluationResult:
        """Evaluate an action against all rules.

        Args:
            action: A dict describing the agent action, e.g.:
                {"action_type": "data_access", "resource_type": "customer_db",
                 "agent_id": "agent-1", "user_id": "user-1"}

        Returns:
            EvaluationResult with the effective decision.

        """
        matched: list[PolicyRule] = []

        for rule in self._rules:
            if self._matches(rule.conditions, action):
                matched.append(rule)

        if not matched:
            return EvaluationResult(effect=RuleEffect.ALLOW, details="No matching rules — allowed by default")

        # DENY rules take precedence over ALLOW/AUDIT at the same priority
        deny_rules = [r for r in matched if r.effect == RuleEffect.DENY]
        if deny_rules:
            highest_deny = max(deny_rules, key=lambda r: r.priority)
            return EvaluationResult(
                effect=RuleEffect.DENY,
                matched_rule=highest_deny.name,
                matched_rules=[r.name for r in matched],
                details=f"Denied by rule: {highest_deny.description}",
            )

        # AUDIT rules take next precedence
        audit_rules = [r for r in matched if r.effect == RuleEffect.AUDIT]
        if audit_rules:
            highest_audit = max(audit_rules, key=lambda r: r.priority)
            return EvaluationResult(
                effect=RuleEffect.AUDIT,
                matched_rule=highest_audit.name,
                matched_rules=[r.name for r in matched],
                details=f"Audited by rule: {highest_audit.description}",
            )

        # ALLOW (lowest precedence)
        allow_rules = [r for r in matched if r.effect == RuleEffect.ALLOW]
        if allow_rules:
            highest_allow = max(allow_rules, key=lambda r: r.priority)
            return EvaluationResult(
                effect=RuleEffect.ALLOW,
                matched_rule=highest_allow.name,
                matched_rules=[r.name for r in matched],
                details=f"Allowed by rule: {highest_allow.description}",
            )

        return EvaluationResult(effect=RuleEffect.ALLOW, details="Allowed by default")

    @staticmethod
    def _matches(conditions: dict[str, Any], action: dict[str, Any]) -> bool:
        """Check if an action matches rule conditions.

        All conditions must match (AND logic). Empty conditions match everything.
        """
        if not conditions:
            return True

        for key, value in conditions.items():
            action_value = action.get(key)
            if action_value is None or action_value != value:
                return False

        return True

    def list_rules(self) -> list[PolicyRule]:
        """List all registered rules in priority order."""
        return list(self._rules)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < initial_count

    def clear(self) -> None:
        """Remove all rules."""
        self._rules.clear()
