"""SBOM (Software Bill of Materials) generator.

Generates SPDX 2.3 compliant SBOMs from project dependency information.
Supports Python projects using pyproject.toml + lock files.
Integrates with vulnerability databases for package scanning.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Dependency:
    """A single dependency identified in the project."""

    name: str
    version: str
    source: str = "unknown"
    license: str = "unknown"


@dataclass
class Vulnerability:
    """A known vulnerability found in a dependency."""

    package: str
    version: str
    cve_id: str = ""
    severity: str = "unknown"
    description: str = ""


@dataclass
class SBOMResult:
    """Result of SBOM generation."""

    project_name: str = ""
    project_version: str = ""
    format: str = "SPDX"
    spdx_id: str = ""
    dependencies: list[Dependency] = field(default_factory=list)
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Known vulnerability database (simplified — in production, query OSV.dev API)
_KNOWN_VULNERABILITIES: dict[str, list[dict[str, Any]]] = {
    "old-package": [
        {
            "cve": "CVE-2024-0001",
            "max_version": "1.0.0",
            "severity": "high",
            "desc": "Remote code execution in old-package",
        },
    ],
}


class SBOMGenerator:
    """Generates SPDX-compliant SBOMs for the platform."""

    def generate(self, project_root: str | Path) -> SBOMResult:
        """Generate an SBOM for a project.

        Args:
            project_root: Root directory of the project.

        Returns:
            SBOMResult with dependencies and vulnerabilities.

        """
        root = Path(project_root)
        result = SBOMResult()
        result.project_name = self._get_project_name(root)
        result.project_version = self._get_project_version(root)
        result.spdx_id = f"SPDXRef-{uuid.uuid4().hex[:12]}"

        deps = self._parse_pyproject_deps(root)
        deps.extend(self._parse_lockfile_deps(root))
        result.dependencies = deps

        result.vulnerabilities = self.check_vulnerabilities(deps)

        return result

    def _get_project_name(self, root: Path) -> str:
        """Extract project name from pyproject.toml or default."""
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            m = re.search(r'name\s*=\s*"([^"]+)"', content)
            if m:
                return m.group(1)
        return Path(root).name or "unknown-project"

    def _get_project_version(self, root: Path) -> str:
        """Extract project version from pyproject.toml or default."""
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            m = re.search(r'version\s*=\s*"([^"]+)"', content)
            if m:
                return m.group(1)
        return "0.0.0"

    def _parse_pyproject_deps(self, root: Path) -> list[Dependency]:
        """Parse dependencies from pyproject.toml."""
        deps: list[Dependency] = []
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return deps

        content = pyproject.read_text()

        # Extract dependencies section
        in_deps = False
        bracket_depth = 0
        deps_text = ""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("dependencies = ["):
                in_deps = True
                bracket_depth += stripped.count("[") - stripped.count("]")
                deps_text += stripped[stripped.index("[") :] + "\n"
            elif in_deps:
                bracket_depth += stripped.count("[") - stripped.count("]")
                deps_text += stripped + "\n"
                if bracket_depth <= 0:
                    break

        if not deps_text:
            return deps

        # Parse individual dependency strings
        dep_entries = re.findall(
            r'"([^"]+)"', deps_text.split("=", 1)[-1] if "=" in deps_text else deps_text
        )

        for entry in dep_entries:
            # Parse "package>=version" or "package==version" or "package"
            m = re.match(r"([\w\-_.]+)(?:[><=!]+\s*([\w.*]+))?", entry)
            if m:
                name = m.group(1)
                version = m.group(2) or "*"
                deps.append(Dependency(name=name, version=version, source="pypi"))

        return deps

    def _parse_lockfile_deps(self, root: Path) -> list[Dependency]:
        """Parse dependencies from uv.lock or poetry.lock."""
        deps: list[Dependency] = []

        # Try uv.lock (TOML format)
        lock = root / "uv.lock"
        if lock.exists():
            content = lock.read_text()
            # Parse [[package]] entries
            package_pattern = re.compile(
                r'\[\[package\]\]\s*\nname\s*=\s*"([^"]+)"\s*\nversion\s*=\s*"([^"]+)"\s*\nsource\s*=\s*"([^"]+)"'
            )
            for m in package_pattern.finditer(content):
                if m.group(1) not in {d.name for d in deps}:
                    deps.append(
                        Dependency(
                            name=m.group(1),
                            version=m.group(2),
                            source=m.group(3),
                        )
                    )

        return deps

    def check_vulnerabilities(self, deps: list[Dependency]) -> list[Vulnerability]:
        """Check dependencies against known vulnerability database.

        In production, this should query OSV.dev API or use Trivy.
        """
        vulns: list[Vulnerability] = []
        for dep in deps:
            if dep.name in _KNOWN_VULNERABILITIES:
                for known_vuln in _KNOWN_VULNERABILITIES[dep.name]:
                    if dep.version <= known_vuln["max_version"]:
                        vulns.append(
                            Vulnerability(
                                package=dep.name,
                                version=dep.version,
                                cve_id=known_vuln["cve"],
                                severity=known_vuln["severity"],
                                description=known_vuln["desc"],
                            )
                        )
        return vulns

    def export_spdx_json(
        self, result: SBOMResult, output_path: str | Path
    ) -> dict[str, Any]:
        """Export SBOM as SPDX 2.3 JSON."""
        packages = [
            {
                "SPDXID": f"SPDXRef-Package-{d.name}",
                "name": d.name,
                "versionInfo": d.version,
                "supplier": f"Organization: {d.source}",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
            }
            for d in result.dependencies
        ]

        doc = {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": result.spdx_id,
            "name": f"{result.project_name}-{result.project_version}",
            "creationInfo": {
                "created": result.generated_at.isoformat(),
                "creators": ["Tool: turin-platform-sbom-0.1.0"],
            },
            "dataLicense": "CC0-1.0",
            "documentNamespace": f"https://github.com/iknowkungfubar/agentic-business-platform/sbom/{uuid.uuid4()}",
            "packages": packages,
            "relationships": [
                {
                    "spdxElementId": result.spdx_id,
                    "relatedSpdxElement": f"SPDXRef-Package-{p['name']}",
                    "relationshipType": "CONTAINS",
                }
                for p in packages
            ],
        }

        with open(output_path, "w") as f:
            json.dump(doc, f, indent=2)

        return doc

    def summary(self, result: SBOMResult) -> str:
        """Generate a human-readable summary of the SBOM."""
        lines = [
            f"SBOM Summary: {result.project_name} v{result.project_version}",
            f"  Format: {result.format}",
            f"  Dependencies: {len(result.dependencies)}",
            f"  Vulnerabilities: {len(result.vulnerabilities)}",
        ]
        if result.vulnerabilities:
            for v in result.vulnerabilities:
                lines.append(f"    [{v.severity.upper()}] {v.cve_id}: {v.description}")
        return "\n".join(lines)
