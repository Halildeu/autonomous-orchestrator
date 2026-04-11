"""Contract tests for impact analyzer (Phase 3).

Validates:
  - Module name conversion
  - Direct importer detection
  - Direct import detection
  - Affected test detection
  - Risk level assessment
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("src.ops.impact_analyzer", reason="impact_analyzer not yet implemented")

from src.ops.impact_analyzer import analyze_impact, _path_to_module, _assess_risk


class TestPathToModule:
    def test_src_ops(self) -> None:
        assert _path_to_module("src/ops/context_compiler.py") == "src.ops.context_compiler"

    def test_nested(self) -> None:
        assert _path_to_module("src/orchestrator/runner.py") == "src.orchestrator.runner"

    def test_no_extension(self) -> None:
        assert _path_to_module("src/ops/foo") == "src.ops.foo"


class TestRiskAssessment:
    def test_low(self) -> None:
        assert _assess_risk(0) == "LOW"
        assert _assess_risk(3) == "LOW"

    def test_medium(self) -> None:
        assert _assess_risk(4) == "MEDIUM"
        assert _assess_risk(8) == "MEDIUM"

    def test_high(self) -> None:
        assert _assess_risk(9) == "HIGH"
        assert _assess_risk(20) == "HIGH"

    def test_critical(self) -> None:
        assert _assess_risk(21) == "CRITICAL"


class TestAnalyzeImpact:
    def test_returns_structure(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = analyze_impact(repo, "src/ops/context_compiler.py")
        assert "target" in result
        assert "direct_importers" in result
        assert "direct_imports" in result
        assert "affected_tests" in result
        assert "affected_count" in result
        assert "risk_level" in result
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_finds_importers_of_compiler(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = analyze_impact(repo, "src/ops/context_compiler.py")
        # enforcement_pre_write.py imports context_compiler
        importers = result["direct_importers"]
        assert any("enforcement_pre_write" in p for p in importers)

    def test_finds_imports_of_compiler(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = analyze_impact(repo, "src/ops/context_compiler.py")
        imports = result["direct_imports"]
        assert any("src.shared.utils" in m for m in imports)

    def test_finds_affected_tests(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = analyze_impact(repo, "src/ops/context_compiler.py")
        tests = result["affected_tests"]
        assert any("test_context_compiler" in t for t in tests)

    def test_nonexistent_file(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = analyze_impact(repo, "src/ops/nonexistent_xyz_42.py")
        # No file to read imports from, and unlikely any file imports this
        assert result["direct_imports"] == []
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
