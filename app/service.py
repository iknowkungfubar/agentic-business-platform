"""Shared service layer — unified interface for CLI and API consumers.

Both app/cli.py and app/routers/* call through this layer instead of
importing directly from core.*, ensuring auth, validation, and error
handling are consistent regardless of entry point.
"""

from __future__ import annotations

from core.governance.policy import EvaluationResult, PolicyEngine
from core.governance.templates import PolicyTemplates
from core.hardening.sbom import SBOMGenerator, SBOMResult
from core.pipeline.ingest import Document, DocumentIngester
from core.router.intent import IntentClassifier, IntentResult
from core.router.selector import ModelSelector, RouteResult
from core.security.mcp_scanner import MCPScanner, ScanResult

# ── Pipeline ──────────────────────────────────────────────────


def ingest_document(path: str) -> Document:
    """Ingest a document from a file path."""
    ingester = DocumentIngester()
    return ingester.ingest(path)


# ── Router ────────────────────────────────────────────────────


def classify_text(text: str) -> IntentResult:
    """Classify the intent of a text input."""
    classifier = IntentClassifier()
    return classifier.classify(text)


def route_text(text: str) -> tuple[IntentResult, RouteResult]:
    """Classify intent and select a model tier."""
    classifier = IntentClassifier()
    selector = ModelSelector()
    intent = classifier.classify(text)
    route = selector.select(intent, text)
    return intent, route


# ── Governance ────────────────────────────────────────────────


def evaluate_action(action: dict) -> EvaluationResult:
    """Evaluate an action against CMMC policies."""
    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())
    return engine.evaluate(action)


# ── Security ──────────────────────────────────────────────────


def scan_mcp_server(url: str, timeout: float = 5.0) -> ScanResult:
    """Scan an MCP server for security issues."""
    scanner = MCPScanner(timeout=timeout)
    return scanner.scan(url)


# ── Hardening ─────────────────────────────────────────────────


def generate_sbom(project_root: str = ".") -> SBOMResult:
    """Generate an SBOM for a project."""
    generator = SBOMGenerator()
    return generator.generate(project_root=project_root)
