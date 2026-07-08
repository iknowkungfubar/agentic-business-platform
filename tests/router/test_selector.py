"""Unit tests for the model selector."""

from __future__ import annotations

import pytest

from core.router.intent import IntentResult
from core.router.selector import ModelSelector


class TestModelSelector:
    @pytest.fixture
    def selector(self):
        return ModelSelector()

    def test_simple_qa_routes_to_t1(self, selector):
        """Simple Q&A should route to T1 (small model)."""
        intent = IntentResult(intent_type="question_answering", confidence=0.8, reason="test")
        route = selector.select(intent, "What is the capital of France?")
        assert route.model_tier == "t1"

    def test_summarization_routes_to_t1(self, selector):
        """Summarization should route to T1."""
        intent = IntentResult(intent_type="summarization", confidence=0.8, reason="test")
        route = selector.select(intent, "Summarize this short text.")
        assert route.model_tier == "t1"

    def test_data_extraction_routes_to_t2(self, selector):
        """Data extraction should route to T2 by default."""
        intent = IntentResult(intent_type="data_extraction", confidence=0.8, reason="test")
        route = selector.select(intent, "Extract all names from this document")
        assert route.model_tier == "t2"

    def test_code_generation_routes_to_t3(self, selector):
        """Code generation should route to T3."""
        intent = IntentResult(intent_type="code_generation", confidence=0.8, reason="test")
        route = selector.select(intent, "def hello():\n    print('hi')")
        assert route.model_tier == "t3"

    def test_analysis_routes_to_t3(self, selector):
        """Analysis should route to T3."""
        intent = IntentResult(intent_type="analysis", confidence=0.7, reason="test")
        route = selector.select(intent, "Analyze the data distribution across regions")
        assert route.model_tier == "t3"

    def test_large_content_upgrades_tier(self, selector):
        """Very large content should upgrade to a higher tier."""
        intent = IntentResult(intent_type="question_answering", confidence=0.8, reason="test")
        large_content = "word " * 2000  # ~8000 chars → ~2000 tokens
        route = selector.select(intent, large_content)
        # Large content should upgrade from T1 to at least T3
        assert route.model_tier == "t3"

    def test_complexity_keywords_upgrade_tier(self, selector):
        """Content with complexity keywords should upgrade tier."""
        intent = IntentResult(intent_type="question_answering", confidence=0.8, reason="test")
        route = selector.select(intent, "What is the optimal distributed architecture for concurrent processing?")
        # Should be upgraded from T1 due to complexity keywords
        assert route.model_tier in ("t2", "t3")

    def test_low_confidence_defaults_to_t1(self, selector):
        """Low confidence intent should default to T1."""
        intent = IntentResult(intent_type="unknown", confidence=0.1, reason="test")
        route = selector.select(intent, "some random text")
        assert route.model_tier == "t1"

    def test_route_result_has_reason(self, selector):
        """Route result should include reasoning."""
        intent = IntentResult(intent_type="code_generation", confidence=0.9, reason="test")
        route = selector.select(intent, "def foo(): pass")
        assert route.reason is not None
        assert len(route.reason) > 0

    def test_route_result_has_estimated_tokens(self, selector):
        """Route result should include estimated token count."""
        intent = IntentResult(intent_type="question_answering", confidence=0.8, reason="test")
        route = selector.select(intent, "hello world")
        assert route.estimated_tokens > 0
