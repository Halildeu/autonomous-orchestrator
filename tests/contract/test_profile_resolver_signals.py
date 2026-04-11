"""Contract tests for context_profile_resolver signal gathering fixes.

Phase 0 — Bug fixes:
  - overall_status: resolver must read 'overall_status' (not 'status') from system_status.v1.json
  - manual_request.kind: resolver must load latest manual request kind for auto-resolution

Tests use subprocess isolation to avoid pytest import cache interference.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_HELPER = """\
import json, sys
from pathlib import Path
sys.path.insert(0, {repo_root!r})
from src.ops.context_profile_resolver import _gather_context_signals
signals = _gather_context_signals(Path({workspace!r}))
print(json.dumps(signals))
"""


def _run_gather(workspace: Path) -> dict:
    """Run _gather_context_signals in a subprocess for clean isolation."""
    code = _HELPER.format(repo_root=str(REPO_ROOT), workspace=str(workspace))
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, f"subprocess failed: {r.stderr}"
    return json.loads(r.stdout)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with cache structure."""
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index" / "manual_requests").mkdir(parents=True)
    return ws


# ── overall_status bug fix ──────────────────────────────────────


class TestOverallStatusSignal:
    """Resolver must read 'overall_status' field, not 'status'."""

    def test_reads_overall_status_field(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"overall_status": "FAIL", "version": "v1"},
        )
        signals = _run_gather(workspace)
        assert signals["system_status"]["overall_status"] == "FAIL"

    def test_fallback_to_status_field_if_overall_missing(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"status": "WARN", "version": "v1"},
        )
        signals = _run_gather(workspace)
        assert signals["system_status"]["overall_status"] == "WARN"

    def test_default_ok_when_both_missing(self, workspace: Path) -> None:
        _write_json(
            workspace / ".cache" / "reports" / "system_status.v1.json",
            {"version": "v1"},
        )
        signals = _run_gather(workspace)
        assert signals["system_status"]["overall_status"] == "OK"

    def test_no_status_file(self, workspace: Path) -> None:
        signals = _run_gather(workspace)
        assert "system_status" not in signals


# ── manual_request.kind signal ──────────────────────────────────


class TestManualRequestKindSignal:
    """Resolver must load kind from latest manual request."""

    def test_loads_kind_from_latest_request(self, workspace: Path) -> None:
        req_dir = workspace / ".cache" / "index" / "manual_requests"
        _write_json(req_dir / "req_001.json", {"kind": "review"})
        _write_json(req_dir / "req_002.json", {"kind": "assessment"})
        signals = _run_gather(workspace)
        assert signals["manual_request"]["kind"] == "assessment"

    def test_empty_kind_when_no_requests(self, workspace: Path) -> None:
        signals = _run_gather(workspace)
        assert signals["manual_request"]["kind"] == ""

    def test_empty_kind_when_dir_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "no_ws"
        ws.mkdir()
        signals = _run_gather(ws)
        assert signals["manual_request"]["kind"] == ""


# ── integration: resolve_profile uses fixed signals ─────────────


class TestResolveProfileIntegration:
    """Ensure resolve_profile returns valid result with fixed signals."""

    def test_resolve_returns_valid_structure(self, workspace: Path) -> None:
        code = f"""\
import json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from src.ops.context_profile_resolver import resolve_profile
result = resolve_profile(Path({str(workspace)!r}))
print(json.dumps(result, default=str))
"""
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 0, f"subprocess failed: {r.stderr}"
        result = json.loads(r.stdout)
        assert result["version"] == "v1"
        assert "profile_id" in result
        assert "resolution_method" in result
        assert result["resolution_method"] in ("explicit", "auto", "default", "fallback")

    def test_resolve_with_explicit_profile(self, workspace: Path) -> None:
        code = f"""\
import json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from src.ops.context_profile_resolver import resolve_profile
result = resolve_profile(Path({str(workspace)!r}), explicit_profile="EMERGENCY")
print(json.dumps(result, default=str))
"""
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 0, f"subprocess failed: {r.stderr}"
        result = json.loads(r.stdout)
        assert "profile_id" in result
