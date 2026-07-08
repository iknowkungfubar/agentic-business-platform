"""Intent classifier — determines the type of task from text content.

Classifies text into one of several intent categories:
- summarization
- question_answering
- data_extraction
- code_generation
- analysis
- search
- classification
- creative_writing
- unknown
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent_type: str
    confidence: float
    reason: str = ""


class IntentClassifier:
    """Classifies text content into task intents using keyword analysis.

    Uses keyword/pattern matching with confidence scoring. In production,
    this should be replaced with a model-based classifier for higher accuracy.
    """

    # Intent patterns: (intent_type, keywords, weight)
    _PATTERNS: list[tuple[str, list[str], float]] = [
        ("code_generation", [
            "def ", "class ", "function", "import ", "return ",
            "const ", "let ", "var ", "=>", "->", "::", "<T>",
            "#include", "impl ", "fn ", "pub ", "async ", "await",
            "__name__", "__main__", "if __name__", "sys.argv",
        ], 0.8),
        ("code_generation", [
            "write code", "implement", "function that", "method that",
            "generate code", "script", "program",
        ], 0.7),
        ("summarization", [
            "summarize", "summary", "tl;dr", "in short",
            "briefly", "overview of", "key points",
            "executive summary",
        ], 0.8),
        ("question_answering", [
            "what is", "how to", "why does", "when did",
            "where can", "who is", "which one", "explain",
            "define", "tell me about", "meaning of",
        ], 0.7),
        ("data_extraction", [
            "extract", "parse", "scrape", "collect",
            "gather data", "pull data", "get all", "find all",
        ], 0.7),
        ("analysis", [
            "analyze", "analysis", "evaluate", "compare",
            "assess", "metrics", "statistics", "correlation",
            "trend", "pattern", "distribution",
        ], 0.7),
        ("search", [
            "search for", "find", "look up", "query",
            "retrieve", "fetch", "get information about",
        ], 0.7),
        ("classification", [
            "classify", "categorize", "label", "sort",
            "organize", "tag", "assign category",
        ], 0.7),
        ("creative_writing", [
            "write a story", "poem", "creative", "narrative",
            "fiction", "dialogue", "script", "short story",
            "write a tale", "once upon a time",
        ], 0.7),
    ]

    def classify(self, text: str) -> IntentResult:
        """Classify the intent of the given text.

        Args:
            text: The text content to classify.

        Returns:
            IntentResult with the most likely intent type, confidence, and reason.

        """
        if not text or not text.strip():
            return IntentResult(
                intent_type="unknown",
                confidence=0.0,
                reason="Empty or blank text",
            )

        text_lower = text.lower()
        scores: dict[str, float] = {}

        for intent_type, keywords, weight in self._PATTERNS:
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[intent_type] = scores.get(intent_type, 0) + weight
                    break  # One match per pattern group

        if not scores:
            return IntentResult(
                intent_type="question_answering",
                confidence=0.3,
                reason="No specific intent detected, defaulting to Q&A",
            )

        # Get the highest-scoring intent
        best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_intent]

        # Normalize confidence to [0, 1]
        confidence = min(best_score / max(scores.values(), default=1), 1.0)

        return IntentResult(
            intent_type=best_intent,
            confidence=round(confidence, 2),
            reason=f"Matched {len(scores)} intent pattern(s)",
        )
