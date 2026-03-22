"""Contract test for context drift detection (P6).

Tests: artifact drift, session drift, policy drift detection.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.ops.context_drift import detect_context_drift, detect_policy_drift, detect_session_drift
from src.session.context_store import new_context, save_context_atomic, upsert_decision


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {msg}")
        raise SystemExit(2)


def test_artifact_drift_clean() -> None:
    """Both workspaces have identical artifacts → status OK."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        tgt = Path(td) / "target"
        rel = ".cache/index/test_artifact.v1.json"
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (tgt / rel).parent.mkdir(parents=True, exist_ok=True)
        content = '{"version": "v1"}\n'
        (src / rel).write_text(content)
        (tgt / rel).write_text(content)

        result = detect_context_drift(source_workspace=src, target_workspace=tgt, artifact_paths=[rel])
        _assert(result["status"] == "OK", f"expected OK, got {result['status']}")
        _assert(result["drifted_count"] == 0, f"expected 0 drifted, got {result['drifted_count']}")
        _assert(result["artifacts"][0]["action"] == "in_sync", "expected in_sync")
    print("OK test_artifact_drift_clean")


def test_artifact_drift_detected() -> None:
    """Different content → status WARN/FAIL, drifted_count > 0."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        tgt = Path(td) / "target"
        rel = ".cache/index/test_artifact.v1.json"
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (tgt / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text('{"version": "v1", "data": "new"}\n')
        (tgt / rel).write_text('{"version": "v1", "data": "old"}\n')

        result = detect_context_drift(source_workspace=src, target_workspace=tgt, artifact_paths=[rel])
        _assert(result["drifted_count"] == 1, f"expected 1 drifted, got {result['drifted_count']}")
        _assert(result["artifacts"][0]["action"] == "drifted", "expected drifted action")
    print("OK test_artifact_drift_detected")


def test_artifact_missing_in_target() -> None:
    """Artifact exists in source but not target → drifted."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        tgt = Path(td) / "target"
        rel = ".cache/index/test_artifact.v1.json"
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        tgt.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text('{"version": "v1"}\n')

        result = detect_context_drift(source_workspace=src, target_workspace=tgt, artifact_paths=[rel])
        _assert(result["drifted_count"] == 1, "expected 1 drifted (missing)")
        _assert(result["missing_in_target"] == 1, "expected 1 missing_in_target")
    print("OK test_artifact_missing_in_target")


def test_session_drift_clean() -> None:
    """Parent and child have same decisions → OK."""
    with tempfile.TemporaryDirectory() as td:
        parent_ws = Path(td) / "parent"
        child_ws = Path(td) / "child"

        parent_ctx = new_context("default", str(parent_ws), 604800)
        upsert_decision(parent_ctx, key="route:CP-001", value={"bucket": "TICKET"}, source="agent")
        p_path = parent_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        child_ctx = new_context("default", str(child_ws), 604800)
        upsert_decision(child_ctx, key="route:CP-001", value={"bucket": "TICKET"}, source="agent")
        c_path = child_ws / ".cache/sessions/default/session_context.v1.json"
        c_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(c_path, child_ctx)

        result = detect_session_drift(parent_workspace=parent_ws, child_workspace=child_ws)
        _assert(result["status"] == "OK", f"expected OK, got {result['status']}")
        _assert(result["missing_in_child"] == 0, "expected 0 missing")
        _assert(result["conflict_count"] == 0, "expected 0 conflicts")
    print("OK test_session_drift_clean")


def test_session_drift_missing_decisions() -> None:
    """Parent has decisions child doesn't → missing_in_child > 0."""
    with tempfile.TemporaryDirectory() as td:
        parent_ws = Path(td) / "parent"
        child_ws = Path(td) / "child"

        parent_ctx = new_context("default", str(parent_ws), 604800)
        upsert_decision(parent_ctx, key="route:CP-001", value={"bucket": "TICKET"}, source="agent")
        upsert_decision(parent_ctx, key="exec:RUN-001", value={"result": "OK"}, source="agent")
        p_path = parent_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        child_ctx = new_context("default", str(child_ws), 604800)
        c_path = child_ws / ".cache/sessions/default/session_context.v1.json"
        c_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(c_path, child_ctx)

        result = detect_session_drift(parent_workspace=parent_ws, child_workspace=child_ws)
        _assert(result["missing_in_child"] == 2, f"expected 2 missing, got {result['missing_in_child']}")
        _assert(result["status"] in ("WARN", "FAIL"), f"expected WARN/FAIL, got {result['status']}")
    print("OK test_session_drift_missing_decisions")


def test_session_drift_child_missing() -> None:
    """Child session doesn't exist → FAIL."""
    with tempfile.TemporaryDirectory() as td:
        parent_ws = Path(td) / "parent"
        child_ws = Path(td) / "child"
        child_ws.mkdir(parents=True, exist_ok=True)

        parent_ctx = new_context("default", str(parent_ws), 604800)
        p_path = parent_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        result = detect_session_drift(parent_workspace=parent_ws, child_workspace=child_ws)
        _assert(result["status"] == "FAIL", f"expected FAIL, got {result['status']}")
        _assert(result["child_exists"] is False, "expected child_exists=False")
    print("OK test_session_drift_child_missing")


def test_policy_drift_clean() -> None:
    """Same policy files → OK."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        tgt = Path(td) / "target"
        rel = "policies/policy_test.v1.json"
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (tgt / rel).parent.mkdir(parents=True, exist_ok=True)
        content = '{"version": "v1", "enabled": true}\n'
        (src / rel).write_text(content)
        (tgt / rel).write_text(content)

        result = detect_policy_drift(source_root=src, target_root=tgt, policy_paths=[rel])
        _assert(result["status"] == "OK", f"expected OK, got {result['status']}")
        _assert(result["drifted_count"] == 0, "expected 0 drifted")
    print("OK test_policy_drift_clean")


def test_policy_drift_detected() -> None:
    """Different policy content → drifted."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source"
        tgt = Path(td) / "target"
        rel = "policies/policy_test.v1.json"
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (tgt / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text('{"version": "v1", "enabled": true}\n')
        (tgt / rel).write_text('{"version": "v1", "enabled": false}\n')

        result = detect_policy_drift(source_root=src, target_root=tgt, policy_paths=[rel])
        _assert(result["drifted_count"] == 1, f"expected 1 drifted, got {result['drifted_count']}")
        _assert(result["drifted_policies"][0]["action"] == "drifted", "expected drifted action")
    print("OK test_policy_drift_detected")


def main() -> int:
    test_artifact_drift_clean()
    test_artifact_drift_detected()
    test_artifact_missing_in_target()
    test_session_drift_clean()
    test_session_drift_missing_decisions()
    test_session_drift_child_missing()
    test_policy_drift_clean()
    test_policy_drift_detected()
    print(json.dumps({"status": "OK", "tests_passed": 8}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
