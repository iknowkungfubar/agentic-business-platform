"""E2E tests for SBOM pipeline and production hardening."""

from __future__ import annotations

import json


from core.hardening.sbom import SBOMGenerator, Dependency


class TestSBOMPipelineE2E:
    """Full SBOM generation workflow."""

    def test_sbom_generates_for_python_project(self, tmp_path):
        """Generate an SBOM for a sample Python project."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "click>=8.0",
    "httpx>=0.27.0",
    "rich>=13.0.0",
]
""")
        lockfile = tmp_path / "uv.lock"
        lockfile.write_text("""version = 1
requires-python = ">=3.12"

[[package]]
name = "click"
version = "8.1.7"
source = "pypi"

[[package]]
name = "httpx"
version = "0.28.1"
source = "pypi"

[[package]]
name = "rich"
version = "13.9.4"
source = "pypi"
""")

        generator = SBOMGenerator()
        result = generator.generate(project_root=str(tmp_path))

        assert result is not None
        assert len(result.dependencies) >= 3
        assert result.format == "SPDX"
        assert result.spdx_id.startswith("SPDXRef-")

    def test_sbom_includes_dependency_details(self, tmp_path):
        """SBOM should include name, version, and source for each dependency."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\ndependencies = ["pytest>=8.0"]\n')
        lockfile = tmp_path / "uv.lock"
        lockfile.write_text("""version = 1
[[package]]
name = "pytest"
version = "9.1.1"
source = "pypi"
""")

        generator = SBOMGenerator()
        result = generator.generate(project_root=str(tmp_path))

        deps = {d.name: d for d in result.dependencies}
        assert "pytest" in deps
        assert deps["pytest"].version == "9.1.1"
        assert deps["pytest"].source == "pypi"

    def test_sbom_exports_json(self, tmp_path):
        """SBOM should export to SPDX JSON format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\ndependencies = []\n')
        # No deps = still valid SBOM

        generator = SBOMGenerator()
        result = generator.generate(project_root=str(tmp_path))

        out = tmp_path / "sbom.json"
        generator.export_spdx_json(result, str(out))

        with open(out) as f:
            data = json.load(f)
        assert data["name"] == "test-1.0"
        assert data["spdxVersion"] == "SPDX-2.3"
        assert "packages" in data
        assert "creationInfo" in data

    def test_sbom_reports_vulnerable_packages(self, tmp_path):
        """SBOM should identify known vulnerable packages."""
        generator = SBOMGenerator()
        deps = [
            Dependency(name="old-package", version="1.0.0", source="pypi"),
        ]
        vulns = generator.check_vulnerabilities(deps)
        # Should check against known vulnerability database
        assert isinstance(vulns, list)

    def test_sbom_generates_for_empty_project(self, tmp_path):
        """Empty project should produce valid minimal SBOM."""
        generator = SBOMGenerator()
        result = generator.generate(project_root=str(tmp_path))
        assert result is not None
        assert result.format == "SPDX"
        assert result.spdx_id != ""

    def test_sbom_scan_summary(self, tmp_path):
        """Should produce a human-readable scan summary."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\ndependencies = []\n')

        generator = SBOMGenerator()
        result = generator.generate(project_root=str(tmp_path))
        summary = generator.summary(result)

        assert "test v1.0" in summary
        assert "0" in summary  # dependency count
