"""E2E integration tests for governance: policy → eval → red-team."""

from __future__ import annotations


import pytest

from core.governance.policy import PolicyEngine, PolicyRule, RuleEffect
from core.governance.templates import PolicyTemplates
from core.governance.eval import AgentEvalSuite, EvalCriterion, Scorecard
from core.governance.redteam import RedTeamScheduler


class TestGovernanceE2E:
    """Full governance pipeline: define policies → evaluate action → run eval → schedule red-team."""

    def test_full_governance_workflow(self):
        """Define policies, evaluate an action, run eval, schedule red-team."""
        # 1. Create policy engine with CMMC-derived rules
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule(
                name="block_data_exfiltration",
                description="Block agent actions that access sensitive data without approval",
                effect=RuleEffect.DENY,
                conditions={
                    "action_type": "data_access",
                    "resource_type": "sensitive_document",
                },
                priority=10,
            )
        )
        engine.add_rule(
            PolicyRule(
                name="audit_all_inferences",
                description="All model inference must be audited",
                effect=RuleEffect.AUDIT,
                conditions={"action_type": "inference"},
            )
        )

        # 2. Evaluate an action — should be DENIED
        action = {
            "action_type": "data_access",
            "resource_type": "sensitive_document",
            "agent_id": "agent-1",
        }
        result = engine.evaluate(action)
        assert result.effect == RuleEffect.DENY
        assert result.matched_rule == "block_data_exfiltration"

        # 3. Evaluate an allowed action — should PASS or AUDIT
        action2 = {
            "action_type": "health_check",
            "resource_type": "agent",
            "agent_id": "agent-1",
        }
        result2 = engine.evaluate(action2)
        assert result2.effect in (RuleEffect.ALLOW, RuleEffect.AUDIT)

        # 4. Create eval suite and score an agent output
        suite = AgentEvalSuite()
        suite.add_criterion(
            EvalCriterion(
                name="correctness",
                description="Output matches expected result",
                weight=0.5,
            )
        )
        suite.add_criterion(
            EvalCriterion(
                name="safety",
                description="Output contains no harmful content",
                weight=0.3,
            )
        )
        suite.add_criterion(
            EvalCriterion(
                name="compliance",
                description="Output complies with regulatory policies",
                weight=0.2,
            )
        )

        scorecard = suite.evaluate(
            agent_id="agent-1",
            task="Generate a summary of Q3 financial results",
            output="Revenue grew 15% in Q3, exceeding targets. Key drivers: new product launch and expanded market share.",
            scores={"correctness": 0.9, "safety": 1.0, "compliance": 0.8},
        )

        assert isinstance(scorecard, Scorecard)
        assert scorecard.agent_id == "agent-1"
        assert scorecard.weighted_score > 0
        assert scorecard.weighted_score <= 1.0

        # 5. Schedule a red-team test
        scheduler = RedTeamScheduler()
        test = scheduler.schedule(
            agent_id="agent-1",
            test_type="prompt_injection",
            description="Test agent resistance to prompt injection attacks",
        )

        assert test.id is not None
        assert test.agent_id == "agent-1"
        assert test.test_type == "prompt_injection"
        assert test.status == "scheduled"

        # 6. Complete the red-team test
        result = scheduler.complete_test(
            test_id=test.id,
            passed=True,
            findings=[
                "Agent correctly rejected injected prompt",
                "Blocked unauthorized data access",
            ],
        )

        assert result.status == "completed"
        assert result.passed is True
        assert len(result.findings) == 2

    def test_policy_templates_loaded(self):
        """Load policy templates for all frameworks."""
        templates = PolicyTemplates()
        cmmc_rules = templates.get_cmmc_rules()
        gdpr_rules = templates.get_gdpr_rules()
        eu_ai_rules = templates.get_eu_ai_act_rules()

        assert len(cmmc_rules) > 0
        assert len(gdpr_rules) > 0
        assert len(eu_ai_rules) > 0

    def test_deny_overrides_allow(self):
        """DENY rules should take precedence over ALLOW rules."""
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule(
                name="allow_all",
                description="Allow all actions",
                effect=RuleEffect.ALLOW,
                conditions={},
                priority=1,
            )
        )
        engine.add_rule(
            PolicyRule(
                name="deny_data_access",
                description="Deny data access actions",
                effect=RuleEffect.DENY,
                conditions={"action_type": "data_access"},
                priority=10,
            )
        )

        action = {"action_type": "data_access", "resource_type": "customer_db"}
        result = engine.evaluate(action)
        assert result.effect == RuleEffect.DENY
        assert result.matched_rule == "deny_data_access"

    def test_eval_weighted_scoring(self):
        """Weighted scoring should compute correctly."""
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("correctness", weight=0.5))
        suite.add_criterion(EvalCriterion("safety", weight=0.5))

        scorecard = suite.evaluate(
            agent_id="agent-1",
            task="test",
            output="test",
            scores={"correctness": 1.0, "safety": 0.5},
        )

        assert scorecard.weighted_score == pytest.approx(0.75)  # 1.0*0.5 + 0.5*0.5

    def test_red_team_test_history(self):
        """Red-team should track test history."""
        scheduler = RedTeamScheduler()
        t1 = scheduler.schedule("agent-1", "prompt_injection", "Test 1")
        t2 = scheduler.schedule("agent-1", "data_extraction", "Test 2")

        scheduler.complete_test(t1.id, passed=True, findings=["OK"])
        scheduler.complete_test(t2.id, passed=False, findings=["Failed to block extraction"])

        history = scheduler.get_history(agent_id="agent-1")
        assert len(history) == 2

        stats = scheduler.get_stats(agent_id="agent-1")
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
