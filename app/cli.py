"""TurinTech Agentic Business Platform — CLI entry point.

All operations go through app.service (the shared seam) so the CLI
and API behave identically.
"""

from __future__ import annotations

import argparse
import json
import sys

from app import service


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turin-platform",
        description="TurinTech Agentic Business Platform — pipeline, router, governance, security, hardening",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    ingest_p = sub.add_parser("ingest", help="Ingest a document")
    ingest_p.add_argument("path", type=str, help="Path to the document file")
    ingest_p.add_argument("--json", action="store_true", help="Output as JSON")

    classify_p = sub.add_parser("classify", help="Classify text intent")
    classify_p.add_argument("text", type=str, help="Text to classify")

    route_p = sub.add_parser("route", help="Classify intent and select model tier")
    route_p.add_argument("text", type=str, help="Text to route")

    eval_p = sub.add_parser("evaluate", help="Evaluate an action against policies")
    eval_p.add_argument("action", type=str, help="Action JSON to evaluate")

    scan_p = sub.add_parser("scan-mcp", help="Scan an MCP server for security issues")
    scan_p.add_argument("url", type=str, help="MCP server URL to scan")
    scan_p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout")

    sbom_p = sub.add_parser("sbom", help="Generate SBOM for a project")
    sbom_p.add_argument("--output", "-o", type=str, default="sbom.json", help="Output file")
    sbom_p.add_argument("--project-root", type=str, default=".", help="Project root directory")

    return parser


def cmd_ingest(path: str, as_json: bool = False) -> None:
    try:
        service.ingest_document(path)
        if as_json:
            pass
        else:
            pass
    except (FileNotFoundError, ValueError):
        sys.exit(1)


def cmd_classify(text: str) -> None:
    service.classify_text(text)


def cmd_route(text: str) -> None:
    _intent, _route = service.route_text(text)


def cmd_evaluate(action_json: str) -> None:
    try:
        action = json.loads(action_json)
    except json.JSONDecodeError:
        sys.exit(1)

    service.evaluate_action(action)


def cmd_scan_mcp(url: str, timeout: float = 5.0) -> None:
    try:
        result = service.scan_mcp_server(url, timeout=timeout)
    except ValueError:
        sys.exit(1)

    from core.security.mcp_scanner import FindingSeverity

    {
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

    critical = sum(1 for f in result.findings if f.severity == FindingSeverity.CRITICAL)
    high = sum(1 for f in result.findings if f.severity == FindingSeverity.HIGH)
    if critical or high:
        pass


def cmd_sbom(output: str, project_root: str = ".") -> None:
    result = service.generate_sbom(project_root=project_root)
    from core.hardening.sbom import SBOMGenerator

    SBOMGenerator().export_spdx_json(result, output)
    if result.vulnerabilities:
        for _v in result.vulnerabilities:
            pass
    else:
        pass


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
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
