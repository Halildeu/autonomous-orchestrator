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

    from src.session.context_store import (
        SessionContextError,
        load_context,
        new_context,
        save_context_atomic,
        upsert_actor_state,
    )

    passed = 0
    failed = 0

    # --- T1: upsert_actor_state sets all fields correctly ---
    try:
        ctx = new_context("test-actor-1", "/tmp/ws", ttl_seconds=3600)
        upsert_actor_state(
            ctx,
            role="planner",
            actor="claude-code-1",
            provider="claude",
            model="claude-opus-4-6",
            target_id="dev:web",
            selection_reason="policy_default",
            fallback_used=False,
        )
        a = ctx["actor_state"]
        assert a["role"] == "planner", f"role={a['role']}"
        assert a["actor"] == "claude-code-1", f"actor={a['actor']}"
        assert a["provider"] == "claude", f"provider={a['provider']}"
        assert a["model"] == "claude-opus-4-6", f"model={a['model']}"
        assert a["target_id"] == "dev:web", f"target_id={a.get('target_id')}"
        assert a["selection_reason"] == "policy_default", f"sel={a.get('selection_reason')}"
        assert a.get("fallback_used") is None or a.get("fallback_used") is False
        assert "updated_at" in a
        print("T1 PASS: upsert_actor_state sets fields correctly")
        passed += 1
    except Exception as e:
        print(f"T1 FAIL: {e}")
        failed += 1

    # --- T2: invalid role raises SessionContextError ---
    try:
        ctx2 = new_context("test-actor-2", "/tmp/ws", ttl_seconds=3600)
        raised = False
        try:
            upsert_actor_state(ctx2, role="invalid_role", actor="a", provider="p", model="m")
        except SessionContextError as exc:
            raised = True
            assert exc.error_code == "INVALID_ARGS"
        assert raised, "Expected SessionContextError for invalid role"
        print("T2 PASS: invalid role raises SessionContextError")
        passed += 1
    except Exception as e:
        print(f"T2 FAIL: {e}")
        failed += 1

    # --- T3: missing required field raises error ---
    try:
        ctx3 = new_context("test-actor-3", "/tmp/ws", ttl_seconds=3600)
        raised = False
        try:
            upsert_actor_state(ctx3, role="planner", actor="", provider="p", model="m")
        except SessionContextError:
            raised = True
        assert raised, "Expected error for empty actor"
        print("T3 PASS: empty actor raises error")
        passed += 1
    except Exception as e:
        print(f"T3 FAIL: {e}")
        failed += 1

    # --- T4: save + load roundtrip with actor_state ---
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            ctx4 = new_context("test-actor-4", str(ws), ttl_seconds=3600)
            upsert_actor_state(
                ctx4, role="implementer", actor="codex-1",
                provider="openai", model="gpt-5.3-codex",
            )
            path = ws / ".cache" / "sessions" / "test-actor-4" / "session_context.v1.json"
            save_context_atomic(path, ctx4)
            loaded = load_context(path)
            a = loaded["actor_state"]
            assert a["role"] == "implementer"
            assert a["actor"] == "codex-1"
            assert a["provider"] == "openai"
            assert a["model"] == "gpt-5.3-codex"
        print("T4 PASS: save + load roundtrip with actor_state")
        passed += 1
    except Exception as e:
        print(f"T4 FAIL: {e}")
        failed += 1

    # --- T5: existing session without actor_state loads fine ---
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            ctx5 = new_context("test-actor-5", str(ws), ttl_seconds=3600)
            # No actor_state set
            path = ws / ".cache" / "sessions" / "test-actor-5" / "session_context.v1.json"
            save_context_atomic(path, ctx5)
            loaded = load_context(path)
            assert "actor_state" not in loaded
        print("T5 PASS: session without actor_state loads fine (backward compat)")
        passed += 1
    except Exception as e:
        print(f"T5 FAIL: {e}")
        failed += 1

    # --- T6: all 8 valid roles accepted ---
    try:
        valid_roles = [
            "architect", "planner", "implementer", "reviewer",
            "verifier", "consultant", "assurance_owner", "operator",
        ]
        for r in valid_roles:
            ctx6 = new_context(f"test-role-{r}", "/tmp/ws", ttl_seconds=3600)
            upsert_actor_state(ctx6, role=r, actor="test", provider="test", model="test")
            assert ctx6["actor_state"]["role"] == r
        print(f"T6 PASS: all {len(valid_roles)} valid roles accepted")
        passed += 1
    except Exception as e:
        print(f"T6 FAIL: {e}")
        failed += 1

    # --- T7: fallback_used=True is recorded ---
    try:
        ctx7 = new_context("test-actor-7", "/tmp/ws", ttl_seconds=3600)
        upsert_actor_state(
            ctx7, role="planner", actor="a", provider="p", model="m",
            fallback_used=True,
        )
        assert ctx7["actor_state"]["fallback_used"] is True
        print("T7 PASS: fallback_used=True recorded")
        passed += 1
    except Exception as e:
        print(f"T7 FAIL: {e}")
        failed += 1

    # --- T8: optional fields omitted when empty ---
    try:
        ctx8 = new_context("test-actor-8", "/tmp/ws", ttl_seconds=3600)
        upsert_actor_state(ctx8, role="reviewer", actor="a", provider="p", model="m")
        a = ctx8["actor_state"]
        assert "target_id" not in a, "target_id should be omitted when empty"
        assert "selection_reason" not in a, "selection_reason should be omitted when empty"
        assert "fallback_used" not in a, "fallback_used should be omitted when False"
        print("T8 PASS: optional fields omitted when empty")
        passed += 1
    except Exception as e:
        print(f"T8 FAIL: {e}")
        failed += 1

    print(f"\n{'='*40}")
    print(f"Actor State Contract: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
