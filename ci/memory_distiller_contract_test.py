"""Contract test for P2: Memory Distillation."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.session.context_store import new_context, save_context_atomic, upsert_decision
from src.session.memory_distiller import consolidate_facts, distill_decisions_from_sessions, run_distillation


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {msg}")
        raise SystemExit(2)


def _create_session(ws: Path, session_id: str, decisions: list[tuple[str, str]]) -> None:
    ctx = new_context(session_id, str(ws), 604800)
    for key, val in decisions:
        upsert_decision(ctx, key=key, value=val, source="agent")
    sp_path = ws / ".cache" / "sessions" / session_id / "session_context.v1.json"
    sp_path.parent.mkdir(parents=True, exist_ok=True)
    save_context_atomic(sp_path, ctx)


def test_stable_key_promoted() -> None:
    """Same key in 3 sessions with same value → promoted."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        _create_session(ws, "s1", [("route:main", "TICKET"), ("local:s1", "only_s1")])
        _create_session(ws, "s2", [("route:main", "TICKET"), ("local:s2", "only_s2")])
        _create_session(ws, "s3", [("route:main", "TICKET")])

        distilled = distill_decisions_from_sessions(workspace_root=ws, min_occurrences=2, min_stability=2)
        keys = [d["key"] for d in distilled]
        _assert("route:main" in keys, "stable key should be promoted")
        _assert("local:s1" not in keys, "single-session key should NOT be promoted")
        _assert("local:s2" not in keys, "single-session key should NOT be promoted")
    print("OK test_stable_key_promoted")


def test_unstable_key_not_promoted() -> None:
    """Key with different value each session → not promoted."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        _create_session(ws, "s1", [("bucket:test", "TICKET")])
        _create_session(ws, "s2", [("bucket:test", "PROJECT")])
        _create_session(ws, "s3", [("bucket:test", "INCIDENT")])

        distilled = distill_decisions_from_sessions(workspace_root=ws, min_occurrences=2, min_stability=2)
        keys = [d["key"] for d in distilled]
        _assert("bucket:test" not in keys, "unstable key should NOT be promoted")
    print("OK test_unstable_key_not_promoted")


def test_consolidation_merge() -> None:
    """Consolidation merges new facts with existing store."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)

        # Pre-existing fact
        facts_path = ws / ".cache" / "index" / "workspace_facts.v1.json"
        facts_path.parent.mkdir(parents=True, exist_ok=True)
        facts_path.write_text(json.dumps({
            "version": "v1",
            "generated_at": "2026-01-01T00:00:00Z",
            "total_facts": 1,
            "distillation_runs": 1,
            "facts": [{
                "key": "existing:fact",
                "value": "old_value",
                "confidence": 0.8,
                "first_seen": "2026-01-01T00:00:00Z",
                "last_confirmed": "2026-01-01T00:00:00Z",
                "occurrences": 5,
                "source_sessions": ["s0"],
            }],
        }, indent=2) + "\n")

        # New distilled facts
        distilled = [
            {
                "key": "new:fact",
                "value": "new_value",
                "confidence": 0.9,
                "first_seen": "2026-03-01T00:00:00Z",
                "last_confirmed": "2026-03-01T00:00:00Z",
                "occurrences": 3,
                "source_sessions": ["s1", "s2"],
            },
        ]

        result = consolidate_facts(workspace_root=ws, distilled=distilled)
        _assert(result["total_facts"] == 2, f"expected 2 facts, got {result['total_facts']}")
        _assert(result["new_facts"] == 1, f"expected 1 new, got {result['new_facts']}")

        # Verify stored
        stored = json.loads(facts_path.read_text())
        keys = [f["key"] for f in stored["facts"]]
        _assert("existing:fact" in keys, "existing fact should be preserved")
        _assert("new:fact" in keys, "new fact should be added")
    print("OK test_consolidation_merge")


def test_full_pipeline() -> None:
    """End-to-end: sessions → distill → consolidate → fact store."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        _create_session(ws, "s1", [("config:mode", "production"), ("temp:x", "1")])
        _create_session(ws, "s2", [("config:mode", "production"), ("temp:y", "2")])

        result = run_distillation(workspace_root=ws, min_occurrences=2, min_stability=2)
        _assert(result["status"] == "OK", f"expected OK, got {result['status']}")
        _assert(result["distilled_candidates"] >= 1, "expected at least 1 candidate")

        # Verify fact store exists
        facts_path = ws / ".cache" / "index" / "workspace_facts.v1.json"
        _assert(facts_path.exists(), "fact store should exist")

        store = json.loads(facts_path.read_text())
        _assert(store["version"] == "v1", "version should be v1")
    print("OK test_full_pipeline")


def test_schema_validation() -> None:
    """Fact store validates against workspace-facts schema."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        _create_session(ws, "s1", [("key:a", "val")])
        _create_session(ws, "s2", [("key:a", "val")])

        run_distillation(workspace_root=ws, min_occurrences=2, min_stability=2)

        from jsonschema import Draft202012Validator
        schema_path = _REPO_ROOT / "schemas" / "workspace-facts.schema.v1.json"
        schema = json.loads(schema_path.read_text())
        facts_path = ws / ".cache" / "index" / "workspace_facts.v1.json"
        data = json.loads(facts_path.read_text())
        errors = list(Draft202012Validator(schema).iter_errors(data))
        _assert(not errors, f"schema validation failed: {errors[0].message if errors else ''}")
    print("OK test_schema_validation")


def main() -> int:
    test_stable_key_promoted()
    test_unstable_key_not_promoted()
    test_consolidation_merge()
    test_full_pipeline()
    test_schema_validation()
    print(json.dumps({"status": "OK", "tests_passed": 5}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
