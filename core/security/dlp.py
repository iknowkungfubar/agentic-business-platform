"""Data Loss Prevention (DLP) pipeline — PII detection, masking, and unmasking.

Uses regex patterns to detect sensitive data (SSN, credit cards, emails, API keys)
before they reach the LLM inference pipeline. Implements the masking pattern:
replace sensitive values with tokens, store the mapping, and unmask on output.

This ensures the LLM never "sees" real PII — a zero-trust requirement for
CMMC 2.0, EU AI Act, and HIPAA compliance.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from typing import Any

# ── PII Detection Patterns ────────────────────────────────────

# Ordered by specificity — more specific patterns first to avoid partial matches
PI_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # SSN: 123-45-6789 or 123456789
    ("SSN", "Social Security Number", re.compile(r"\b(\d{3}-?\d{2}-?\d{4})\b")),
    # Credit Card: 16-digit with optional dashes/spaces
    ("CREDIT_CARD", "Credit Card Number", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
    # Email addresses
    ("EMAIL", "Email Address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # API Keys: common patterns (sk-, pk-, tok_, tp_, etc.)
    ("API_KEY", "API Key / Token", re.compile(r"\b(sk[-_]|pk[-_]|tok_|tp_|ghp_|gho_|ghu_)[A-Za-z0-9_-]{20,}\b")),
    # Phone numbers: US/International with optional country code
    ("PHONE", "Phone Number", re.compile(r"\b(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b")),
    # IP addresses
    ("IP_ADDRESS", "IP Address", re.compile(r"\b(\d{1,3}\.){3}\d{1,3}\b")),
]


class DLPResult:
    """Result of DLP analysis — masked text + secure mapping."""

    def __init__(self, masked_text: str, mapping: dict[str, str], findings: list[dict[str, Any]]):
        self.masked_text = masked_text
        self.mapping = mapping  # {token: original_value}
        self.findings = findings  # [{type, token, start, end}]


def analyze(text: str) -> DLPResult:
    """Analyze text for PII and produce a masked version with mapping.

    Args:
        text: Raw input text that may contain PII.

    Returns:
        DLPResult with masked_text (PII replaced by [REDACTED_TYPE_N] tokens),
        mapping (token → original value dict), and findings list.
    """
    masked = text
    mapping: dict[str, str] = {}
    findings: list[dict[str, Any]] = []
    counters: dict[str, int] = {}

    for pii_type, description, pattern in PI_PATTERNS:

        def make_replacer(pii_type: str, mapping: dict, counters: dict, findings: list) -> callable:
            def replacer(match: re.Match) -> str:
                original = match.group(0)
                counters.setdefault(pii_type, 0)
                counters[pii_type] += 1
                token = f"[REDACTED_{pii_type}_{counters[pii_type]}]"
                mapping[token] = original
                findings.append(
                    {
                        "type": pii_type,
                        "description": description,
                        "token": token,
                        "original_length": len(original),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
                return token

            return replacer

        masked = pattern.sub(make_replacer(pii_type, mapping, counters, findings), masked)

    return DLPResult(masked_text=masked, mapping=mapping, findings=findings)


def unmask(text: str, mapping: dict[str, str]) -> str:
    """Replace [REDACTED_*] tokens back with the original values.

    Args:
        text: Text that may contain redaction tokens.
        mapping: Dictionary mapping tokens to original values.

    Returns:
        Text with tokens replaced by original values.
    """
    result = text
    # Sort by token length (longest first) to avoid partial replacements
    for token in sorted(mapping.keys(), key=len, reverse=True):
        result = result.replace(token, mapping[token])
    return result


def serialize_mapping(mapping: dict[str, str]) -> str:
    """Serialize the DLP mapping to JSON for Redis storage."""
    return json.dumps(mapping)


def deserialize_mapping(data: str) -> dict[str, str]:
    """Deserialize the DLP mapping from JSON."""
    if not data:
        return {}
    return json.loads(data)
