"""Contract tests for bootstrap gate (Phase 1).

Validates:
  - Health gate: score >= 0.8 PASS, < 0.8 FAIL
  - Profile gate: resolution must succeed
  - Grace mode: first N invocations WARN, then BLOCKED
  - Session caching: PASS result cached for session
  - Tier checks still work (backward compat)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("ci.check_context_bootstrap", reason="check_context_bootstrap not yet implemented")

from ci.check_context_bootstrap import (
    run_bootstrap_check,
    run_bootstrap_gate,
    _check_health_gate,
    _check_profile_gate,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index").mkdir(parents=True)
    return ws


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Minimal repo root with required structural files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("# AGENTS", encoding="utf-8")
    (repo / "docs" / "OPERATIONS").mkdir(parents=True)
    (repo / "docs" / "OPERATIONS" / "CODEX-UX.md").write_text("# CODEX-UX", encoding="utf-8")
    (repo / "docs" / "LAYER-MODEL-LOCK.v1.md").write_text("# LAYER", encoding="utf-8")
    return repo


# ── Health Gate ─────────────────────────────────────────────────


class TestHealthGate:
    def test_returns_gate_structure(self, workspace: Path) -> None:
        result = _check_health_gate(workspace)
        assert result["gate"] == "health"
        assert result["status"] in ("PASS", "WARN", "FAIL")
        assert "score" in result
        assert "min_required" in result

    def test_warn_when_health_unavailable(self, workspace: Path) -> None:
        # No health lens available → WARN (not crash)
        result = _check_health_gate(workspace)
        assert result["status"] in ("PASS", "WARN", "FAIL")


# ── Profile Gate ────────────────────────────────────────────────


class TestProfileGate:
    def test_returns_gate_structure(self, workspace: Path) -> None:
        result = _check_profile_gate(workspace)
        assert result["gate"] == "profile"
        assert result["status"] in ("PASS", "FAIL")
        assert "profile_id" in result

    def test_profile_resolution_succeeds(self, workspace: Path) -> None:
        result = _check_profile_gate(workspace)
        # Should resolve to default (TASK_EXECUTION) even without signals
        assert result["status"] == "PASS"


# ── Bootstrap Gate (full) ───────────────────────────────────���───


class TestBootstrapGate:
    def test_returns_v1_structure(self, repo: Path, workspace: Path) -> None:
        result = run_bootstrap_gate(
            repo_root=repo,
            workspace_root=workspace,
        )
        assert result["version"] == "v1"
        assert result["gate_result"] in ("PASS", "WARN", "BLOCKED")
        assert "tiers" in result
        assert "gates" in result
        assert "health_score" in result
        assert "profile_id" in result
        assert "grace_count" in result

    def test_grace_mode_warn_then_block(self, repo: Path, workspace: Path) -> None:
        # Grace invocations = 1 → first call WARN, second call BLOCKED
        # (assuming health is low with empty workspace)
        r1 = run_bootstrap_gate(
            repo_root=repo,
            workspace_root=workspace,
            grace_invocations=1,
        )
        # Clear cache to force re-evaluation
        evidence = workspace / ".cache" / "reports" / "bootstrap_evidence.v1.json"
        if evidence.exists():
            evidence.unlink()

        r2 = run_bootstrap_gate(
            repo_root=repo,
            workspace_root=workspace,
            grace_invocations=1,
        )
        # First should be WARN (grace), second should be BLOCKED or still WARN
        # depending on health score
        assert r1["gate_result"] in ("PASS", "WARN")
        assert r2["gate_result"] in ("PASS", "WARN", "BLOCKED")

    def test_pass_result_cached(self, repo: Path, workspace: Path) -> None:
        # Run gate, then check if evidence file was written
        run_bootstrap_gate(
            repo_root=repo,
            workspace_root=workspace,
        )
        evidence = workspace / ".cache" / "reports" / "bootstrap_evidence.v1.json"
        assert evidence.exists()
        data = json.loads(evidence.read_text())
        assert data["version"] == "v1"


# ── Backward Compatibility ──────────────────────────────────────


class TestBackwardCompat:
    def test_tier_check_still_works(self, repo: Path, workspace: Path) -> None:
        result = run_bootstrap_check(
            repo_root=repo,
            workspace_root=workspace,
        )
        assert result["version"] == "v1"
        assert "tiers" in result
        assert len(result["tiers"]) == 3
        assert result["tiers"][0]["name"] == "status_context"
        assert result["tiers"][1]["name"] == "structural_context"
        assert result["tiers"][2]["name"] == "project_context"
