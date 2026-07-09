"""TurinTech Agentic Business Platform — CLI entry point.

Exposes all platform capabilities through a unified command-line interface.
"""

from __future__ import annotations

import argparse
import json
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turin-platform",
        description="TurinTech Agentic Business Platform — pipeline, router, governance, security, hardening",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # ingest
    ingest_p = sub.add_parser("ingest", help="Ingest a document")
    ingest_p.add_argument("path", type=str, help="Path to the document file")
    ingest_p.add_argument("--json", action="store_true", help="Output as JSON")

    # classify
    classify_p = sub.add_parser("classify", help="Classify text intent")
    classify_p.add_argument("text", type=str, help="Text to classify")

    # route
    route_p = sub.add_parser("route", help="Classify intent and select model tier")
    route_p.add_argument("text", type=str, help="Text to route")

    # evaluate (policy check)
    eval_p = sub.add_parser("evaluate", help="Evaluate an action against policies")
    eval_p.add_argument("action", type=str, help="Action JSON to evaluate")

    # scan (MCP)
    scan_p = sub.add_parser("scan-mcp", help="Scan an MCP server for security issues")
    scan_p.add_argument("url", type=str, help="MCP server URL to scan")
    scan_p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout")

    # sbom
    sbom_p = sub.add_parser("sbom", help="Generate SBOM for a project")
    sbom_p.add_argument("--output", "-o", type=str, default="sbom.json", help="Output file")
    sbom_p.add_argument("--project-root", type=str, default=".", help="Project root directory")

    return parser


def cmd_ingest(path: str, as_json: bool = False) -> None:
    from core.pipeline.ingest import DocumentIngester

    ingester = DocumentIngester()
    try:
        doc = ingester.ingest(path)
        if as_json:
            print(json.dumps({
                "id": doc.id,
                "source": doc.source,
                "content_length": len(doc.content),
                "content_preview": doc.content[:200],
                "metadata": doc.metadata,
            }, indent=2))
        else:
            print(f"Document: {doc.id}")
            print(f"Source: {doc.source}")
            print(f"Size: {len(doc.content)} chars")
            print(f"Type: {doc.metadata.get('file_type', 'unknown')}")
            print(f"\nPreview:\n{doc.content[:500]}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_classify(text: str) -> None:
    from core.router.intent import IntentClassifier

    classifier = IntentClassifier()
    result = classifier.classify(text)
    print(json.dumps({
        "intent": result.intent_type,
        "confidence": result.confidence,
        "reason": result.reason,
    }, indent=2))


def cmd_route(text: str) -> None:
    from core.router.intent import IntentClassifier
    from core.router.selector import ModelSelector

    classifier = IntentClassifier()
    selector = ModelSelector()

    intent = classifier.classify(text)
    route = selector.select(intent, text)

    print(json.dumps({
        "intent": intent.intent_type,
        "intent_confidence": intent.confidence,
        "model_tier": route.model_tier,
        "route_confidence": route.confidence,
        "estimated_tokens": route.estimated_tokens,
        "reason": route.reason,
    }, indent=2))


def cmd_evaluate(action_json: str) -> None:
    from core.governance.policy import PolicyEngine
    from core.governance.templates import PolicyTemplates

    try:
        action = json.loads(action_json)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    engine = PolicyEngine()
    engine.add_rules(PolicyTemplates.get_cmmc_rules())

    result = engine.evaluate(action)
    print(json.dumps({
        "effect": result.effect.value,
        "matched_rule": result.matched_rule,
        "matched_rules": result.matched_rules,
        "details": result.details,
        "action": action,
    }, indent=2))


def cmd_scan_mcp(url: str, timeout: float = 5.0) -> None:
    from core.security.mcp_scanner import MCPScanner

    scanner = MCPScanner(timeout=timeout)
    try:
        result = scanner.scan(url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.security.mcp_scanner import FindingSeverity
    report_data = {
        "url": result.url,
        "reachable": result.reachable,
        "status_code": result.status_code,
        "is_https": result.is_https,
        "requires_auth": result.requires_auth,
        "findings": [
            {
                "severity": f.severity.value,
                "description": f.description,
                "detail": f.detail,
                "recommendation": f.recommendation,
            }
            for f in result.findings
        ],
    }
    print(json.dumps(report_data, indent=2))

    # Print summary
    critical = sum(1 for f in result.findings if f.severity == FindingSeverity.CRITICAL)
    high = sum(1 for f in result.findings if f.severity == FindingSeverity.HIGH)
    if critical or high:
        print(f"\n⚠️  {critical} critical, {high} high severity issues", file=sys.stderr)


def cmd_sbom(output: str, project_root: str = ".") -> None:
    from core.hardening.sbom import SBOMGenerator

    generator = SBOMGenerator()
    result = generator.generate(project_root=project_root)
    generator.export_spdx_json(result, output)
    print(f"SBOM written to {output}")
    print(f"Dependencies: {len(result.dependencies)}")
    if result.vulnerabilities:
        for v in result.vulnerabilities:
            print(f"  [{v.severity.upper()}] {v.cve_id}: {v.description}")
    else:
        print("  No known vulnerabilities found.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "ingest":
            cmd_ingest(args.path, as_json=args.json)
        elif args.command == "classify":
            cmd_classify(args.text)
        elif args.command == "route":
            cmd_route(args.text)
        elif args.command == "evaluate":
            cmd_evaluate(args.action)
        elif args.command == "scan-mcp":
            cmd_scan_mcp(args.url, timeout=args.timeout)
        elif args.command == "sbom":
            cmd_sbom(args.output, project_root=args.project_root)
        else:
            parser.print_help()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
