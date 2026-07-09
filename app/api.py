"""TurinTech Agentic Business Platform — API server.

Provides a REST interface to all platform capabilities:
- Document ingestion
- Intent classification and model routing
- Policy evaluation
- MCP security scanning
- SBOM generation
"""

from __future__ import annotations


try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    _has_fastapi = True
except ImportError:
    _has_fastapi = False

app = None
if _has_fastapi:
    app = FastAPI(
        title="TurinTech Agentic Business Platform",
        version="0.1.0",
        description="Sovereign AI infrastructure for regulated enterprises",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Models ──────────────────────────────────────────────────────

    class ClassifyRequest(BaseModel):
        text: str

    class RouteRequest(BaseModel):
        text: str

    class EvaluateRequest(BaseModel):
        action: dict

    class ScanMCPRequest(BaseModel):
        url: str
        timeout: float = 5.0

    # ── Routes ───────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/ingest")
    async def ingest(path: str):
        from core.pipeline.ingest import DocumentIngester

        try:
            ingester = DocumentIngester()
            doc = ingester.ingest(path)
            return {
                "id": doc.id,
                "source": doc.source,
                "content_length": len(doc.content),
                "content_preview": doc.content[:500],
                "metadata": doc.metadata,
            }
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/classify")
    async def classify(req: ClassifyRequest):
        from core.router.intent import IntentClassifier

        classifier = IntentClassifier()
        result = classifier.classify(req.text)
        return {
            "intent": result.intent_type,
            "confidence": result.confidence,
            "reason": result.reason,
        }

    @app.post("/route")
    async def route(req: RouteRequest):
        from core.router.intent import IntentClassifier
        from core.router.selector import ModelSelector

        classifier = IntentClassifier()
        selector = ModelSelector()
        intent = classifier.classify(req.text)
        route_result = selector.select(intent, req.text)
        return {
            "intent": intent.intent_type,
            "intent_confidence": intent.confidence,
            "model_tier": route_result.model_tier,
            "route_confidence": route_result.confidence,
            "estimated_tokens": route_result.estimated_tokens,
            "reason": route_result.reason,
        }

    @app.post("/evaluate")
    async def evaluate(req: EvaluateRequest):
        from core.governance.policy import PolicyEngine
        from core.governance.templates import PolicyTemplates

        engine = PolicyEngine()
        engine.add_rules(PolicyTemplates.get_cmmc_rules())
        result = engine.evaluate(req.action)
        return {
            "effect": result.effect.value,
            "matched_rule": result.matched_rule,
            "matched_rules": result.matched_rules,
            "details": result.details,
        }

    @app.post("/scan-mcp")
    async def scan_mcp(req: ScanMCPRequest):
        from core.security.mcp_scanner import MCPScanner

        scanner = MCPScanner(timeout=req.timeout)
        try:
            result = scanner.scan(req.url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "url": result.url,
            "reachable": result.reachable,
            "status_code": result.status_code,
            "is_https": result.is_https,
            "requires_auth": result.requires_auth,
            "server_header": result.server_header,
            "findings": [
                {
                    "severity": f.severity.value,
                    "description": f.description,
                }
                for f in result.findings
            ],
        }

    @app.post("/sbom")
    async def sbom(project_root: str = "."):
        from core.hardening.sbom import SBOMGenerator

        generator = SBOMGenerator()
        result = generator.generate(project_root=project_root)
        return {
            "project_name": result.project_name,
            "project_version": result.project_version,
            "dependencies": [
                {"name": d.name, "version": d.version, "source": d.source}
                for d in result.dependencies
            ],
            "vulnerabilities": [
                {"cve": v.cve_id, "severity": v.severity, "package": v.package, "description": v.description}
                for v in result.vulnerabilities
            ],
        }


def serve(host: str = "127.0.0.1", port: int = 8338) -> None:
    """Start the API server."""
    if not _has_fastapi:
        print("FastAPI is required: pip install fastapi uvicorn")
        return
    import uvicorn
    uvicorn.run(app, host=host, port=port)  # type: ignore[arg-type]
