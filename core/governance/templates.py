"""Policy templates — predefined rule sets for compliance frameworks.

Provides policy rules derived from CMMC 2.0, GDPR, and EU AI Act
requirements that can be loaded into the PolicyEngine.
"""

from __future__ import annotations

from core.governance.policy import PolicyRule, RuleEffect


class PolicyTemplates:
    """Factory for loading policy templates by framework."""

    @staticmethod
    def get_cmmc_rules() -> list[PolicyRule]:
        """CMMC 2.0 Level 2 derived policy rules."""
        return [
            PolicyRule(
                name="cmmc_input_validation",
                description="AI.1.001: Validate all agent inputs against adversarial content",
                effect=RuleEffect.DENY,
                conditions={"requires_input_validation": True},
                priority=10,
            ),
            PolicyRule(
                name="cmmc_access_control",
                description="AI.2.001: All model endpoints require authentication",
                effect=RuleEffect.DENY,
                conditions={"requires_auth": True, "authenticated": False},
                priority=10,
            ),
            PolicyRule(
                name="cmmc_output_monitoring",
                description="AI.3.001: Log all agent outputs for SIEM integration",
                effect=RuleEffect.AUDIT,
                conditions={"action_type": "inference"},
                priority=8,
            ),
            PolicyRule(
                name="cmmc_audit_logging",
                description="AU.2.041: All agent actions must be audited",
                effect=RuleEffect.AUDIT,
                conditions={},
                priority=5,
            ),
            PolicyRule(
                name="cmmc_cui_protection",
                description="AC.1.003: Block CUI access without authorization",
                effect=RuleEffect.DENY,
                conditions={"resource_type": "cui", "authorized": False},
                priority=10,
            ),
            PolicyRule(
                name="cmmc_mfa_required",
                description="IA.2.081: Privileged actions require MFA",
                effect=RuleEffect.DENY,
                conditions={"requires_mfa": True, "mfa_verified": False},
                priority=10,
            ),
        ]

    @staticmethod
    def get_gdpr_rules() -> list[PolicyRule]:
        """GDPR-derived policy rules."""
        return [
            PolicyRule(
                name="gdpr_data_minimization",
                description="Art. 5: Only collect data necessary for the specified purpose",
                effect=RuleEffect.DENY,
                conditions={"action_type": "data_collection", "minimization_verified": False},
                priority=10,
            ),
            PolicyRule(
                name="gdpr_right_to_erasure",
                description="Art. 17: Support deletion of personal data on request",
                effect=RuleEffect.AUDIT,
                conditions={"action_type": "data_deletion"},
                priority=8,
            ),
            PolicyRule(
                name="gdpr_security",
                description="Art. 32: Ensure security of processing",
                effect=RuleEffect.DENY,
                conditions={"action_type": "data_access", "encrypted": False},
                priority=10,
            ),
            PolicyRule(
                name="gdpr_audit_trail",
                description="Art. 5(2): Maintain accountability records",
                effect=RuleEffect.AUDIT,
                conditions={"action_type": "data_access"},
                priority=8,
            ),
        ]

    @staticmethod
    def get_eu_ai_act_rules() -> list[PolicyRule]:
        """EU AI Act-derived policy rules."""
        return [
            PolicyRule(
                name="eu_ai_risk_management",
                description="Art. 9: High-risk AI systems require risk assessment",
                effect=RuleEffect.DENY,
                conditions={"risk_level": "high", "risk_assessment_complete": False},
                priority=10,
            ),
            PolicyRule(
                name="eu_ai_human_oversight",
                description="Art. 14: High-risk decisions require human approval",
                effect=RuleEffect.DENY,
                conditions={"requires_human_oversight": True, "human_approved": False},
                priority=10,
            ),
            PolicyRule(
                name="eu_ai_logging",
                description="Art. 12: Log all high-risk AI system events",
                effect=RuleEffect.AUDIT,
                conditions={"risk_level": "high"},
                priority=9,
            ),
            PolicyRule(
                name="eu_ai_transparency",
                description="Art. 13: Users must be informed they interact with AI",
                effect=RuleEffect.DENY,
                conditions={"action_type": "user_interaction", "disclosure_shown": False},
                priority=8,
            ),
        ]
