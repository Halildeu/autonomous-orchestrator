"""Contract tests for context snapshot (Phase 6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.context_snapshot import create_snapshot


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index" / "consultations" / "requests").mkdir(parents=True)
    return ws


class TestCreateSnapshot:
    def test_returns_v1_structure(self, workspace: Path) -> None:
        snap = create_snapshot(workspace, from_agent="claude", to_agent="codex")
        assert snap["version"] == "v1"
        assert snap["from_agent"] == "claude"
        assert snap["to_agent"] == "codex"
        assert snap["snapshot_id"].startswith("SNAP-")
        assert "compiled_context_hash" in snap
        assert "active_profile" in snap

    def test_includes_scope_state(self, workspace: Path) -> None:
        # Write a scope state
        scope = {"status": "WITHIN_SCOPE", "actual_scope": {"files_count": 3, "domains_touched": ["backend"]}}
        (workspace / ".cache" / "reports" / "scope_guard_state.v1.json").write_text(
            json.dumps(scope), encoding="utf-8"
        )
        snap = create_snapshot(workspace)
        assert snap["scope_state"]["status"] == "WITHIN_SCOPE"
        assert snap["scope_state"]["files_written"] == 3

    def test_includes_quality_metrics(self, workspace: Path) -> None:
        metrics = {"cache_hit_rate": 0.75, "quality_trend": "IMPROVING", "total_writes": 10}
        (workspace / ".cache" / "reports" / "context_session_metrics.v1.json").write_text(
            json.dumps(metrics), encoding="utf-8"
        )
        snap = create_snapshot(workspace)
        assert snap["quality_metrics"]["cache_hit_rate"] == 0.75
        assert snap["quality_metrics"]["quality_trend"] == "IMPROVING"

    def test_finds_pending_consultations(self, workspace: Path) -> None:
        req = {
            "consultation_id": "CNS-20260404-001",
            "status": "OPEN",
            "to_agent": "codex",
            "topic": "architecture",
            "question": "Should we use X?",
        }
        req_path = workspace / ".cache" / "index" / "consultations" / "requests" / "CNS-20260404-001.request.v1.json"
        req_path.write_text(json.dumps(req), encoding="utf-8")

        snap = create_snapshot(workspace, to_agent="codex")
        assert len(snap["pending_consultations"]) == 1
        assert snap["pending_consultations"][0]["consultation_id"] == "CNS-20260404-001"

    def test_writes_snapshot_file(self, workspace: Path) -> None:
        snap = create_snapshot(workspace)
        snap_files = list((workspace / ".cache" / "reports").glob("SNAP-*.v1.json"))
        assert len(snap_files) >= 1

    def test_empty_workspace_still_works(self, tmp_path: Path) -> None:
        ws = tmp_path / "empty"
        ws.mkdir()
        snap = create_snapshot(ws)
        assert snap["version"] == "v1"
        assert snap["active_profile"] == "UNKNOWN"
