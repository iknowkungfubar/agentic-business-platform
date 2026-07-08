"""Model selector — routes tasks to the appropriate model tier.

Four model tiers:
- T1: 9B GGUF (simple tasks: search, summarization, simple Q&A)
- T2: 9B-14B (data extraction, classification, routing)
- T3: 35B+ (code generation, analysis, reasoning)
- T4: 70B+ or cluster (complex multi-step agent tasks)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.router.intent import IntentResult

# Rough estimate: 1 token ≈ 4 characters in English text
_CHARS_PER_TOKEN = 4


@dataclass
class RouteResult:
    """Result of model routing."""

    model_tier: str
    confidence: float
    reason: str = ""
    estimated_tokens: int = 0


class ModelSelector:
    """Selects the appropriate model tier based on task intent and complexity.

    Uses intent type, content complexity (estimated tokens), and domain
    keywords to determine the most cost-effective model tier.
    """

    # Intent → default tier mapping
    _INTENT_TIERS: dict[str, str] = {
        "summarization": "t1",
        "search": "t1",
        "question_answering": "t1",
        "classification": "t1",
        "data_extraction": "t2",
        "analysis": "t3",
        "code_generation": "t3",
        "creative_writing": "t2",
    }

    # Content complexity indicators → tier upgrade
    _COMPLEXITY_KEYWORDS: dict[str, list[str]] = {
        "t3": ["distributed", "concurrent", "optimization", "architecture",
               "algorithm", "protocol", "encryption", "authentication"],
        "t4": ["formal verification", "theorem", "proof", "complex analysis",
               "multi-agent", "autonomous", "planning"],
    }

    def select(self, intent: IntentResult, content: str) -> RouteResult:
        """Select the best model tier for a given intent and content.

        Args:
            intent: The classified intent result.
            content: The text content to process.

        Returns:
            RouteResult with the selected model tier, confidence, and reasoning.

        """
        if intent.intent_type == "unknown" or intent.confidence < 0.3:
            return RouteResult(
                model_tier="t1",
                confidence=0.3,
                reason=f"Low confidence intent ({intent.intent_type}: {intent.confidence}), defaulting to T1",
            )

        # Start with the default tier for this intent type
        base_tier = self._INTENT_TIERS.get(intent.intent_type, "t1")
        final_tier = base_tier

        # Estimate token count
        estimated_tokens = len(content) // _CHARS_PER_TOKEN

        # Upgrade tier based on content size
        if estimated_tokens > 2000 and self._tier_index(final_tier) < 3:
            final_tier = "t3"
            reason_parts = [f"Large content ({estimated_tokens} estimated tokens)"]
        elif estimated_tokens > 500 and self._tier_index(final_tier) < 2:
            final_tier = "t2"
            reason_parts = [f"Medium content ({estimated_tokens} estimated tokens)"]
        else:
            reason_parts = [f"Base tier for intent '{intent.intent_type}'"]

        # Upgrade tier based on complexity keywords
        content_lower = content.lower()
        for tier, keywords in self._COMPLEXITY_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                if self._tier_index(tier) > self._tier_index(final_tier):
                    final_tier = tier
                    reason_parts.append(f"Complexity keywords detected")

        reason_parts.append(f"confidence={intent.confidence}")
        reason = " — ".join(reason_parts)

        # Confidence: base from intent, reduced if we upgraded tiers
        confidence = intent.confidence * (1.0 - 0.1 * abs(self._tier_index(final_tier) - self._tier_index(base_tier)))

        return RouteResult(
            model_tier=final_tier,
            confidence=round(max(confidence, 0.1), 2),
            reason=reason,
            estimated_tokens=estimated_tokens,
        )

    @staticmethod
    def _tier_index(tier: str) -> int:
        """Convert tier string to numeric index for comparison."""
        mapping = {"t1": 1, "t2": 2, "t3": 3, "t4": 4}
        return mapping.get(tier, 1)
