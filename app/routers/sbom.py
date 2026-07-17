"""SBOM generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers import require_role

router = APIRouter(tags=["sbom"])


@router.post("/sbom")
async def generate_sbom(
    project_root: str = ".",
    user: dict = Depends(require_role("operator")),
):
    from core.hardening.sbom import SBOMGenerator

    generator = SBOMGenerator()
    result = generator.generate(project_root=project_root)
    return {
        "project_name": result.project_name,
        "project_version": result.project_version,
        "dependencies": [{"name": d.name, "version": d.version} for d in result.dependencies],
        "vulnerabilities": [
            {"cve": v.cve_id, "severity": v.severity, "package": v.package} for v in result.vulnerabilities
        ],
    }
