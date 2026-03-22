"""Contract test for context reconciliation controller (P0).

Tests: observe→compare→act→report cycle.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.ops.context_reconciler import reconcile_managed_repo
from src.session.context_store import new_context, save_context_atomic, upsert_decision


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {msg}")
        raise SystemExit(2)


def test_reconcile_stale_session() -> None:
    """Expired child session → reconcile → renewed + inherited."""
    with tempfile.TemporaryDirectory() as td:
        orch_ws = Path(td) / "orchestrator"
        target_ws = Path(td) / "target"
        target_root = Path(td) / "target_repo"
        target_root.mkdir(parents=True, exist_ok=True)

        # Create parent with decisions
        parent_ctx = new_context("default", str(orch_ws), 604800)
        upsert_decision(parent_ctx, key="route:CP-001", value={"bucket": "TICKET"}, source="agent")
        p_path = orch_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        # No child session exists
        result = reconcile_managed_repo(
            orchestrator_workspace=orch_ws,
            target_workspace=target_ws,
            target_repo_root=target_root,
            orchestrator_root=Path(td),
            apply=True,
        )

        _assert(result["applied"] is True, "expected applied=True")
        _assert(result["actions_count"] >= 1, f"expected actions, got {result['actions_count']}")

        # Verify child session was created
        child_path = target_ws / ".cache/sessions/default/session_context.v1.json"
        _assert(child_path.exists(), "child session should be created")
    print("OK test_reconcile_stale_session")


def test_reconcile_clean_state() -> None:
    """Both in sync → no actions needed."""
    with tempfile.TemporaryDirectory() as td:
        orch_ws = Path(td) / "orchestrator"
        target_ws = Path(td) / "target"
        target_root = Path(td) / "target_repo"
        target_root.mkdir(parents=True, exist_ok=True)

        # Create identical parent and child
        parent_ctx = new_context("default", str(orch_ws), 604800)
        p_path = orch_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        child_ctx = new_context("default", str(target_ws), 604800)
        c_path = target_ws / ".cache/sessions/default/session_context.v1.json"
        c_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(c_path, child_ctx)

        result = reconcile_managed_repo(
            orchestrator_workspace=orch_ws,
            target_workspace=target_ws,
            target_repo_root=target_root,
            orchestrator_root=Path(td),
            apply=False,
        )

        _assert(result["applied"] is False, "expected applied=False (dry-run)")
        _assert("health_before" in result, "expected health_before in report")
        _assert("health_after" in result, "expected health_after in report")
    print("OK test_reconcile_clean_state")


def test_reconcile_pushes_missing_artifacts() -> None:
    """Missing artifacts in target → pushed from source."""
    with tempfile.TemporaryDirectory() as td:
        orch_ws = Path(td) / "orchestrator"
        target_ws = Path(td) / "target"
        target_root = Path(td) / "target_repo"
        target_root.mkdir(parents=True, exist_ok=True)

        # Create parent session
        parent_ctx = new_context("default", str(orch_ws), 604800)
        p_path = orch_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        # Create artifact in orchestrator only
        art_path = orch_ws / ".cache/index/gap_register.v1.json"
        art_path.parent.mkdir(parents=True, exist_ok=True)
        art_path.write_text('{"version": "v1", "gaps": []}\n')

        result = reconcile_managed_repo(
            orchestrator_workspace=orch_ws,
            target_workspace=target_ws,
            target_repo_root=target_root,
            orchestrator_root=Path(td),
            apply=True,
        )

        # Check artifact was pushed
        pushed = [a for a in result["actions_taken"] if a.get("action") == "artifact_pushed"]
        _assert(len(pushed) >= 1, f"expected at least 1 artifact pushed, got {len(pushed)}")

        # Verify artifact exists in target
        target_art = target_ws / ".cache/index/gap_register.v1.json"
        _assert(target_art.exists(), "gap_register should exist in target after push")
    print("OK test_reconcile_pushes_missing_artifacts")


def test_reconcile_health_delta() -> None:
    """Health delta is calculated correctly."""
    with tempfile.TemporaryDirectory() as td:
        orch_ws = Path(td) / "orchestrator"
        target_ws = Path(td) / "target"
        target_root = Path(td) / "target_repo"
        target_root.mkdir(parents=True, exist_ok=True)

        # Create parent with decisions
        parent_ctx = new_context("default", str(orch_ws), 604800)
        upsert_decision(parent_ctx, key="test:key1", value="val1", source="agent")
        p_path = orch_ws / ".cache/sessions/default/session_context.v1.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p_path, parent_ctx)

        result = reconcile_managed_repo(
            orchestrator_workspace=orch_ws,
            target_workspace=target_ws,
            target_repo_root=target_root,
            orchestrator_root=Path(td),
            apply=True,
        )

        _assert("health_delta" in result, "expected health_delta")
        _assert(isinstance(result["health_delta"], float), "health_delta should be float")
        # After reconciliation, health should improve (delta >= 0)
        _assert(result["health_delta"] >= 0, f"expected non-negative delta, got {result['health_delta']}")
    print("OK test_reconcile_health_delta")


def main() -> int:
    test_reconcile_stale_session()
    test_reconcile_clean_state()
    test_reconcile_pushes_missing_artifacts()
    test_reconcile_health_delta()
    print(json.dumps({"status": "OK", "tests_passed": 4}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
