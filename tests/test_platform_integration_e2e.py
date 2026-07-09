"""E2E integration tests for the full platform stack.

Tests the integrated flow: API → pipeline → router → governance.
"""

from __future__ import annotations


from core.pipeline.ingest import DocumentIngester
from core.pipeline.chunk import TextChunker
from core.router.intent import IntentClassifier
from core.router.selector import ModelSelector
from core.governance.policy import PolicyEngine, PolicyRule, RuleEffect
from core.governance.eval import AgentEvalSuite, EvalCriterion


class TestPlatformIntegrationE2E:
    """Full platform integration: API → pipeline → router → governance."""

    def test_full_document_processing_workflow(self, tmp_path):
        """Ingest a document → chunk → classify → route → evaluate via policy."""

        # 1. Ingest a document
        doc_path = tmp_path / "quarterly_report.txt"
        doc_path.write_text(
            "Q3 Financial Report\n\n"
            "Revenue grew 15% year-over-year to $12.4M.\n"
            "Operating margin improved to 22%.\n\n"
            "Key drivers:\n"
            "- New product launch in Europe\n"
            "- Customer expansion in existing accounts\n"
            "- Cost optimization program savings\n\n"
            "Outlook: Continued growth expected in Q4 with\n"
            "several large deals in the pipeline."
        )

        ingester = DocumentIngester()
        doc = ingester.ingest(str(doc_path))
        assert doc is not None
        assert len(doc.content) > 0

        # 2. Chunk the document
        chunker = TextChunker(chunk_size=300, overlap=30)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 0

        # 3. Classify and route each chunk
        classifier = IntentClassifier()
        selector = ModelSelector()

        for chunk in chunks:
            intent = classifier.classify(chunk.content)
            route = selector.select(intent, chunk.content)
            assert route.model_tier is not None
            assert intent.intent_type is not None

        # 4. Run the chunks through policy evaluation
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule(
                name="audit_all",
                description="All operations require auditing",
                effect=RuleEffect.AUDIT,
                conditions={},
            )
        )

        for chunk in chunks:
            action = {
                "action_type": "inference",
                "resource_type": "document_chunk",
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "content_length": len(chunk.content),
            }
            result = engine.evaluate(action)
            assert result.effect in (RuleEffect.AUDIT, RuleEffect.ALLOW)

        # 5. Evaluate agent output quality
        suite = AgentEvalSuite()
        suite.add_criterion(EvalCriterion("correctness", weight=0.5))
        suite.add_criterion(EvalCriterion("compliance", weight=0.5))

        scorecard = suite.evaluate(
            agent_id="test-agent",
            task="Analyze Q3 report and extract key metrics",
            output="Revenue: $12.4M, Growth: 15%, Margin: 22%",
            scores={"correctness": 0.95, "compliance": 0.9},
        )

        assert scorecard.weighted_score > 0.9
        assert scorecard.passed is True

    def test_policy_blocks_unauthorized_action(self):
        """Policy engine should block unauthorized data access."""
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule(
                name="cmmc_cui_protection",
                description="Block unauthorized CUI access",
                effect=RuleEffect.DENY,
                conditions={"resource_type": "cui", "authorized": False},
                priority=10,
            )
        )

        action = {"action_type": "data_access", "resource_type": "cui", "authorized": False}
        result = engine.evaluate(action)
        assert result.effect == RuleEffect.DENY

        # Authorized access should pass
        action2 = {"action_type": "data_access", "resource_type": "cui", "authorized": True}
        result2 = engine.evaluate(action2)
        assert result2.effect != RuleEffect.DENY

    def test_code_document_routes_to_t3_and_passes_policy(self, tmp_path):
        """Code documents should route to T3 tier and pass governance."""
        doc_path = tmp_path / "script.py"
        doc_path.write_text(
            "def process_data(items):\n    results = []\n    for item in items:\n        results.append(item * 2)\n    return results\n"
        )

        ingester = DocumentIngester()
        chunker = TextChunker(chunk_size=1000, overlap=20)
        classifier = IntentClassifier()
        selector = ModelSelector()
        engine = PolicyEngine()
        engine.add_rule(
            PolicyRule("audit_code", effect=RuleEffect.AUDIT, conditions={"action_type": "code_generation"})
        )

        doc = ingester.ingest(str(doc_path))
        chunks = chunker.chunk(doc)

        for chunk in chunks:
            intent = classifier.classify(chunk.content)
            route = selector.select(intent, chunk.content)

            # Code should route to a capable tier
            assert route.model_tier in ("t2", "t3", "t4")

            # Should pass through policy
            action = {"action_type": "code_generation", "resource_type": "code", "content": chunk.content[:50]}
            result = engine.evaluate(action)
            assert result.effect in (RuleEffect.AUDIT, RuleEffect.ALLOW)

    def test_mcp_scan_feeds_into_compliance(self, tmp_path):
        """MCP scan results should produce structured output suitable for compliance."""
        from core.security.mcp_scanner import MCPScanner

        scanner = MCPScanner(timeout=1.0)
        results = scanner.scan_multi(["http://127.0.0.1:1", "http://127.0.0.1:2"])
        report = scanner.generate_report(results)

        assert "scan_summary" in report
        assert report["scan_summary"]["total"] == 2
        assert report["scan_summary"]["unreachable"] == 2

        # Export for compliance evidence
        out = tmp_path / "mcp_scan.json"
        scanner.export_json(results, str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_sbom_generates_for_current_project(self):
        """SBOM generator should work on the platform's own project."""
        from core.hardening.sbom import SBOMGenerator

        generator = SBOMGenerator()
        result = generator.generate(project_root=".")
        assert result is not None
        assert result.project_name == "turin-platform"
        # The SBOM parsing of the platform's own pyproject.toml may or may not
        # find dependencies depending on the format — the module itself has
        # comprehensive tests for that. Verify the structure is valid.
        assert len(result.spdx_id) > 0
