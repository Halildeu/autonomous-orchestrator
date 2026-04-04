"""Contract tests for context_profile_resolver signal gathering fixes.

Phase 0 — Bug fixes:
  - overall_status: resolver must read 'overall_status' (not 'status') from system_status.v1.json
  - manual_request.kind: resolver must load latest manual request kind for auto-resolution
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.context_profile_resolver import _gather_context_signals, resolve_profile


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with cache structure."""
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index" / "manual_requests").mkdir(parents=True)
    return ws


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ── overall_status bug fix ──────────────────────────────────────


class TestOverallStatusSignal:
    """Resolver must read 'overall_status' field, not 'status'."""

    def test_reads_overall_status_field(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"overall_status": "FAIL", "version": "v1"},
        )
        signals = _gather_context_signals(workspace)
        assert signals["system_status"]["overall_status"] == "FAIL"

    def test_fallback_to_status_field_if_overall_missing(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"status": "WARN", "version": "v1"},
        )
        signals = _gather_context_signals(workspace)
        assert signals["system_status"]["overall_status"] == "WARN"

    def test_default_ok_when_both_missing(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"version": "v1"},
        )
        signals = _gather_context_signals(workspace)
        assert signals["system_status"]["overall_status"] == "OK"

    def test_no_status_file(self, workspace: Path) -> None:
        signals = _gather_context_signals(workspace)
        assert "system_status" not in signals


# ── manual_request.kind signal ──────────────────────────────────


class TestManualRequestKindSignal:
    """Resolver must load kind from latest manual request."""

    def test_loads_kind_from_latest_request(self, workspace: Path) -> None:
        req_dir = workspace / ".cache" / "index" / "manual_requests"
        _write_json(req_dir / "req_001.json", {"kind": "review"})
        _write_json(req_dir / "req_002.json", {"kind": "assessment"})
        signals = _gather_context_signals(workspace)
        # Sorted reverse → req_002 is latest
        assert signals["manual_request"]["kind"] == "assessment"

    def test_empty_kind_when_no_requests(self, workspace: Path) -> None:
        signals = _gather_context_signals(workspace)
        assert signals["manual_request"]["kind"] == ""

    def test_empty_kind_when_dir_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "no_ws"
        ws.mkdir()
        signals = _gather_context_signals(ws)
        assert signals["manual_request"]["kind"] == ""


# ── integration: resolve_profile uses fixed signals ─────────────


class TestResolveProfileIntegration:
    """Ensure resolve_profile returns valid result with fixed signals."""

    def test_resolve_returns_valid_structure(self, workspace: Path) -> None:
        result = resolve_profile(workspace)
        assert result["version"] == "v1"
        assert "profile_id" in result
        assert "resolution_method" in result
        assert result["resolution_method"] in ("explicit", "auto", "default", "fallback")

    def test_resolve_with_explicit_profile(self, workspace: Path) -> None:
        result = resolve_profile(workspace, explicit_profile="EMERGENCY")
        # May fallback if EMERGENCY not in registry, but should not crash
        assert "profile_id" in result
