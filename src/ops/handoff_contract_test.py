from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.handoff_contract import build_handoff_envelope, validate_handoff
    from src.ops.closeout_write import run_closeout_write

    passed = 0
    failed = 0

    # --- T1: build_handoff_envelope produces valid envelope ---
    try:
        envelope = build_handoff_envelope(
            from_role="planner",
            from_actor="claude-code-1",
            from_provider="claude",
            from_model="claude-opus-4-6",
            from_session_id="session-001",
            to_role="implementer",
            work_item_id="WI-001",
            handoff_reason="Planning complete, ready for implementation",
            evidence_paths=[".cache/reports/plan.json"],
        )
        assert envelope["version"] == "v1"
        assert envelope["from_role"] == "planner"
        assert envelope["from_actor"] == "claude-code-1"
        assert envelope["to_role"] == "implementer"
        assert envelope["work_item_id"] == "WI-001"
        assert "handoff_id" in envelope
        assert envelope["handoff_id"].startswith("HO-")
        assert "created_at" in envelope
        print("T1 PASS: build_handoff_envelope produces valid envelope")
        passed += 1
    except Exception as e:
        print(f"T1 FAIL: {e}")
        failed += 1

    # --- T2: validate_handoff returns no errors for valid envelope ---
    try:
        errors = validate_handoff(envelope)
        assert errors == [], f"Expected no errors, got: {errors}"
        print("T2 PASS: validate_handoff returns no errors for valid envelope")
        passed += 1
    except Exception as e:
        print(f"T2 FAIL: {e}")
        failed += 1

    # --- T3: validate_handoff catches invalid role ---
    try:
        bad = dict(envelope)
        bad["from_role"] = "invalid_role"
        errors = validate_handoff(bad)
        assert len(errors) > 0, "Expected validation errors for invalid role"
        print("T3 PASS: validate_handoff catches invalid role")
        passed += 1
    except Exception as e:
        print(f"T3 FAIL: {e}")
        failed += 1

    # --- T4: validate_handoff catches missing required field ---
    try:
        bad2 = dict(envelope)
        del bad2["work_item_id"]
        errors = validate_handoff(bad2)
        assert len(errors) > 0, "Expected validation errors for missing work_item_id"
        print("T4 PASS: validate_handoff catches missing required field")
        passed += 1
    except Exception as e:
        print(f"T4 FAIL: {e}")
        failed += 1

    # --- T5: optional fields (to_actor, scope_glob) are set when provided ---
    try:
        envelope2 = build_handoff_envelope(
            from_role="reviewer",
            from_actor="codex-1",
            from_provider="openai",
            from_model="gpt-5.3-codex",
            from_session_id="session-002",
            to_role="verifier",
            to_actor="claude-verify-1",
            work_item_id="WI-002",
            handoff_reason="Review done",
            evidence_paths=[],
            scope_glob="src/orchestrator/**",
        )
        assert envelope2["to_actor"] == "claude-verify-1"
        assert envelope2["scope_glob"] == "src/orchestrator/**"
        errors = validate_handoff(envelope2)
        assert errors == [], f"Expected no errors, got: {errors}"
        print("T5 PASS: optional fields set correctly")
        passed += 1
    except Exception as e:
        print(f"T5 FAIL: {e}")
        failed += 1

    # --- T6: closeout_write with actor fields ---
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            reports = ws / ".cache" / "reports"
            reports.mkdir(parents=True)
            result = run_closeout_write(
                workspace_root=ws,
                out_path=".cache/reports/test_closeout.json",
                title="Test Closeout",
                evidence_paths=[".cache/reports/plan.json"],
                actor_role="implementer",
                actor="claude-code-1",
                provider="claude",
                model="claude-opus-4-6",
                handoff_from="HO-abc123",
            )
            assert result["status"] == "OK", f"Expected OK, got {result}"
            closeout_path = ws / ".cache" / "reports" / "test_closeout.json"
            data = json.loads(closeout_path.read_text())
            assert data["actor_role"] == "implementer"
            assert data["actor"] == "claude-code-1"
            assert data["provider"] == "claude"
            assert data["model"] == "claude-opus-4-6"
            assert data["handoff_from"] == "HO-abc123"
            assert data["trace_meta"]["actor_role"] == "implementer"
            assert data["trace_meta"]["provider_used"] == "claude"
            assert data["trace_meta"]["model_used"] == "claude-opus-4-6"
        print("T6 PASS: closeout_write with actor + handoff fields")
        passed += 1
    except Exception as e:
        print(f"T6 FAIL: {e}")
        failed += 1

    # --- T7: closeout_write without actor fields still works ---
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            reports = ws / ".cache" / "reports"
            reports.mkdir(parents=True)
            result = run_closeout_write(
                workspace_root=ws,
                out_path=".cache/reports/plain_closeout.json",
                title="Plain Closeout",
                evidence_paths=[],
            )
            assert result["status"] == "OK"
            data = json.loads((ws / ".cache" / "reports" / "plain_closeout.json").read_text())
            assert "actor_role" not in data
            assert "handoff_from" not in data
        print("T7 PASS: closeout_write without actor fields (backward compat)")
        passed += 1
    except Exception as e:
        print(f"T7 FAIL: {e}")
        failed += 1

    print(f"\n{'='*40}")
    print(f"Handoff Contract: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
