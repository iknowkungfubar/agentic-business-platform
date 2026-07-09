"""Unit tests for the policy engine."""

from __future__ import annotations

from core.governance.policy import PolicyEngine, PolicyRule, RuleEffect


class TestPolicyEngine:
    def test_empty_engine_allows_all(self):
        """Engine with no rules should allow all actions."""
        engine = PolicyEngine()
        result = engine.evaluate({"action_type": "any"})
        assert result.effect == RuleEffect.ALLOW

    def test_deny_rule_blocks_matching_action(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("block_test", effect=RuleEffect.DENY, conditions={"action_type": "test"}))
        result = engine.evaluate({"action_type": "test"})
        assert result.effect == RuleEffect.DENY

    def test_allow_rule_passes_non_blocked_action(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("block_test", effect=RuleEffect.DENY, conditions={"action_type": "test"}))
        result = engine.evaluate({"action_type": "health_check"})
        assert result.effect == RuleEffect.ALLOW

    def test_audit_rule_triggers_audit(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("audit_all", effect=RuleEffect.AUDIT, conditions={}))
        result = engine.evaluate({"action_type": "anything"})
        assert result.effect == RuleEffect.AUDIT

    def test_higher_priority_takes_precedence(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("allow_low", effect=RuleEffect.ALLOW, conditions={}, priority=1))
        engine.add_rule(PolicyRule("deny_high", effect=RuleEffect.DENY, conditions={}, priority=10))
        result = engine.evaluate({"action_type": "anything"})
        assert result.effect == RuleEffect.DENY
        assert result.matched_rule == "deny_high"

    def test_multiple_conditions_must_all_match(self):
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule(
                "specific_block",
                effect=RuleEffect.DENY,
                conditions={"action_type": "data_access", "resource_type": "secrets"},
            )
        )
        # Only matches if ALL conditions match
        assert engine.evaluate({"action_type": "data_access", "resource_type": "logs"}).effect == RuleEffect.ALLOW
        assert engine.evaluate({"action_type": "inference", "resource_type": "secrets"}).effect == RuleEffect.ALLOW
        assert engine.evaluate({"action_type": "data_access", "resource_type": "secrets"}).effect == RuleEffect.DENY

    def test_remove_rule(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("test", effect=RuleEffect.DENY, conditions={}))
        assert engine.remove_rule("test") is True
        assert engine.remove_rule("nonexistent") is False

    def test_clear_all_rules(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("r1", effect=RuleEffect.DENY, conditions={}))
        engine.add_rule(PolicyRule("r2", effect=RuleEffect.DENY, conditions={}))
        engine.clear()
        assert len(engine.list_rules()) == 0

    def test_list_rules_in_priority_order(self):
        engine = PolicyEngine()
        engine.add_rule(PolicyRule("low", priority=1))
        engine.add_rule(PolicyRule("high", priority=10))
        engine.add_rule(PolicyRule("medium", priority=5))
        rules = engine.list_rules()
        assert [r.name for r in rules] == ["high", "medium", "low"]

    def test_add_rules_bulk(self):
        engine = PolicyEngine()
        engine.add_rules(
            [
                PolicyRule("r1", effect=RuleEffect.DENY, conditions={"type": "a"}),
                PolicyRule("r2", effect=RuleEffect.AUDIT, conditions={"type": "b"}),
            ]
        )
        assert len(engine.list_rules()) == 2
