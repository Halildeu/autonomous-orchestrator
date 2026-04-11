"""Contract tests for unified context compiler (Phase 1).

Validates:
  - Single assembly layer for Claude + Codex
  - Agent-scoped artifacts (no race condition)
  - Provenance tracking for rules
  - Fingerprint-based caching
  - Legacy backward compatibility
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("src.ops.context_compiler", reason="context_compiler not yet implemented")

from src.ops.context_compiler import (
    compile_enforcement_context,
    clear_cache,
)


@pytest.fixture(autouse=True)
def _clear_compiler_cache() -> None:
    """Clear compiler cache before each test."""
    clear_cache()


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index").mkdir(parents=True)
    return ws


# ── Core compilation ────────────────────────────────────────────


class TestCompileEnforcementContext:
    """Unified compiler produces valid output for any agent."""

    def test_returns_v1_structure(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        assert result["version"] == "v1"
        assert result["agent_id"] == "claude"
        assert result["compiler_version"] == "2.0.0"
        assert "compiled_at" in result
        assert "profile" in result
        assert "authorization" in result
        assert "rules" in result
        assert "fingerprint" in result

    def test_claude_and_codex_same_structure(self, workspace: Path) -> None:
        clear_cache()
        claude = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        clear_cache()
        codex = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="codex",
        )
        # Same keys in output
        assert set(claude.keys()) == set(codex.keys())
        # Same rules (agent doesn't affect rules)
        assert claude["rules"]["domain"] == codex["rules"]["domain"]
        assert claude["rules"]["layer"] == codex["rules"]["layer"]
        # Different agent_id
        assert claude["agent_id"] == "claude"
        assert codex["agent_id"] == "codex"

    def test_profile_resolution_included(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        profile = result["profile"]
        assert "id" in profile
        assert "resolution_method" in profile
        assert profile["resolution_method"] in ("explicit", "auto", "default", "fallback")


# ── Agent-scoped artifacts (R2) ─────────────────────────────────


class TestAgentScopedArtifacts:
    """Agent-scoped artifacts prevent multi-agent race condition."""

    def test_claude_artifact_created(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        fp = result["fingerprint"][:8]
        artifact = workspace / ".cache" / "reports" / f"rule_packet.claude.{fp}.v1.json"
        assert artifact.exists()

    def test_codex_artifact_separate(self, workspace: Path) -> None:
        clear_cache()
        compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        clear_cache()
        compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="codex",
        )
        reports = workspace / ".cache" / "reports"
        claude_files = list(reports.glob("rule_packet.claude.*.v1.json"))
        codex_files = list(reports.glob("rule_packet.codex.*.v1.json"))
        assert len(claude_files) >= 1
        assert len(codex_files) >= 1

    def test_legacy_packet_still_written(self, workspace: Path) -> None:
        compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        legacy = workspace / ".cache" / "reports" / "rule_packet.v1.json"
        assert legacy.exists()
        data = json.loads(legacy.read_text())
        assert data["version"] == "v1"
        assert "authorization" in data
        assert "rules" in data


# ── Provenance tracking ─────────────────────────────────────────


class TestProvenanceTracking:
    """Every rule includes source and why metadata."""

    def test_provenance_list_populated(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        provenance = result.get("rules_with_provenance", [])
        assert isinstance(provenance, list)
        # Should have at least general rules and shared utils
        assert len(provenance) > 0

    def test_provenance_has_required_fields(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        for entry in result.get("rules_with_provenance", []):
            assert "rule_id" in entry
            assert "text" in entry
            assert "source" in entry
            assert "domain" in entry
            assert "profile" in entry
            assert "priority" in entry
            assert entry["priority"] in ("MUST", "SHOULD")

    def test_provenance_rule_ids_unique(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        ids = [r["rule_id"] for r in result.get("rules_with_provenance", [])]
        assert len(ids) == len(set(ids)), f"Duplicate rule IDs: {ids}"


# ── Compilation sources ─────────────────────────────────────────


class TestCompilationSources:
    """Compilation sources track which files contributed."""

    def test_sources_include_core_files(self, workspace: Path) -> None:
        result = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        source_paths = [s["path"] for s in result.get("compilation_sources", [])]
        # Should include at least AGENTS.md (always exists in repo)
        assert any("AGENTS.md" in p for p in source_paths)


# ── Fingerprint caching ─────────────────────────────────────────


class TestFingerprintCaching:
    """Same input produces cache hit on second compilation."""

    def test_cache_hit_on_repeat(self, workspace: Path) -> None:
        result1 = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        result2 = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        assert result1["fingerprint"] == result2["fingerprint"]
        # Same compiled_at (cached, not recomputed)
        assert result1["compiled_at"] == result2["compiled_at"]

    def test_cache_miss_on_different_target(self, workspace: Path) -> None:
        result1 = compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        clear_cache()
        result2 = compile_enforcement_context(
            workspace_root=workspace,
            target_path="policies/test.v1.json",
        )
        assert result1["fingerprint"] != result2["fingerprint"]

    def test_clear_cache(self, workspace: Path) -> None:
        compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
        )
        cleared = clear_cache()
        assert cleared >= 1
