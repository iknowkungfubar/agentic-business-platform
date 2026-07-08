"""Unit tests for the intent classifier."""

from __future__ import annotations

import pytest

from core.router.intent import IntentClassifier


class TestIntentClassifier:
    """Tests for the intent classifier."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_classify_code_generation_def(self, classifier):
        """Functions with def should be classified as code."""
        result = classifier.classify("def hello():\n    return 42")
        assert result.intent_type == "code_generation"
        assert result.confidence >= 0.7

    def test_classify_code_generation_class(self, classifier):
        """Classes should be classified as code."""
        result = classifier.classify("class FooBar:\n    pass")
        assert result.intent_type == "code_generation"

    def test_classify_summarization(self, classifier):
        """Summarization requests should be classified correctly."""
        result = classifier.classify("Please summarize the key findings from this report")
        assert result.intent_type == "summarization"

    def test_classify_question_answering(self, classifier):
        """Questions should be classified as Q&A."""
        result = classifier.classify("What is the capital of France?")
        assert result.intent_type == "question_answering"

    def test_classify_data_extraction(self, classifier):
        """Extraction requests should be classified correctly."""
        result = classifier.classify("Extract all email addresses from this document")
        assert result.intent_type == "data_extraction"

    def test_classify_analysis(self, classifier):
        """Analysis requests should be classified correctly."""
        result = classifier.classify("Analyze the sales trends for Q3")
        assert result.intent_type == "analysis"

    def test_classify_search(self, classifier):
        """Search requests should be classified correctly."""
        result = classifier.classify("Search for documentation about the API")
        assert result.intent_type == "search"

    def test_classify_creative_writing(self, classifier):
        """Creative writing should be classified correctly."""
        result = classifier.classify("Write a short story about a robot learning to paint")
        assert result.intent_type == "creative_writing"

    def test_empty_text_returns_unknown(self, classifier):
        """Empty text should return unknown intent."""
        result = classifier.classify("")
        assert result.intent_type == "unknown"
        assert result.confidence == 0.0

    def test_whitespace_only_returns_unknown(self, classifier):
        """Whitespace-only text should return unknown."""
        result = classifier.classify("   \n  \t  ")
        assert result.intent_type == "unknown"

    def test_nonsense_text_defaults_to_qa(self, classifier):
        """Text with no matching intent should default to Q&A."""
        result = classifier.classify("xylophone zebra quantum")
        assert result.intent_type == "question_answering"
        assert result.confidence == 0.3

    def test_multiple_intents_picks_highest(self, classifier):
        """Text fitting multiple intents should pick the highest confidence."""
        result = classifier.classify("def analyze_data():\n    # Summarize the results\n    pass")
        # Should prefer code_generation over analysis or summarization
        assert result.intent_type == "code_generation"
