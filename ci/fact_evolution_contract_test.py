"""Contract test for P5: Fact Evolution Tracking."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.session.context_store import new_context, save_context_atomic, upsert_decision
from src.ops.fact_evolution import detect_fact_regressions


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {msg}")
        raise SystemExit(2)


def test_history_tracking() -> None:
    """Upsert same key 3x with different values → history length = 2."""
    ctx = new_context("test", "/tmp", 604800)
    upsert_decision(ctx, key="test:key1", value="v1", source="agent")
    upsert_decision(ctx, key="test:key1", value="v2", source="agent")
    upsert_decision(ctx, key="test:key1", value="v3", source="agent")

    d = [x for x in ctx["ephemeral_decisions"] if x["key"] == "test:key1"][0]
    history = d.get("history", [])
    _assert(len(history) == 2, f"expected 2 history entries, got {len(history)}")
    _assert(history[0]["value"] == "v1", f"expected v1 in history[0], got {history[0]['value']}")
    _assert(history[1]["value"] == "v2", f"expected v2 in history[1], got {history[1]['value']}")
    _assert(d["value"] == "v3", f"expected current value v3, got {d['value']}")
    print("OK test_history_tracking")


def test_duplicate_suppression() -> None:
    """Upsert same value → no history entry added."""
    ctx = new_context("test", "/tmp", 604800)
    upsert_decision(ctx, key="test:key1", value="same", source="agent")
    upsert_decision(ctx, key="test:key1", value="same", source="agent")

    d = [x for x in ctx["ephemeral_decisions"] if x["key"] == "test:key1"][0]
    history = d.get("history", [])
    _assert(len(history) == 0, f"expected 0 history (duplicate), got {len(history)}")
    print("OK test_duplicate_suppression")


def test_history_cap() -> None:
    """History capped at 10 entries."""
    ctx = new_context("test", "/tmp", 604800)
    for i in range(15):
        upsert_decision(ctx, key="test:cap", value=f"v{i}", source="agent")

    d = [x for x in ctx["ephemeral_decisions"] if x["key"] == "test:cap"][0]
    history = d.get("history", [])
    _assert(len(history) == 10, f"expected 10 (capped), got {len(history)}")
    _assert(history[0]["value"] == "v4", f"expected v4 as oldest, got {history[0]['value']}")
    print("OK test_history_cap")


def test_regression_detection() -> None:
    """Value reverts to previous → regression detected."""
    ctx = new_context("test", "/tmp", 604800)
    upsert_decision(ctx, key="route:test", value={"bucket": "TICKET"}, source="agent")
    upsert_decision(ctx, key="route:test", value={"bucket": "PROJECT"}, source="agent")
    upsert_decision(ctx, key="route:test", value={"bucket": "TICKET"}, source="agent")  # revert

    regressions = detect_fact_regressions(ctx)
    _assert(len(regressions) == 1, f"expected 1 regression, got {len(regressions)}")
    _assert(regressions[0]["key"] == "route:test", "wrong key in regression")
    print("OK test_regression_detection")


def test_no_regression() -> None:
    """Progressive changes → no regression."""
    ctx = new_context("test", "/tmp", 604800)
    upsert_decision(ctx, key="score:test", value=60, source="agent")
    upsert_decision(ctx, key="score:test", value=72, source="agent")
    upsert_decision(ctx, key="score:test", value=84, source="agent")

    regressions = detect_fact_regressions(ctx)
    _assert(len(regressions) == 0, f"expected 0 regressions, got {len(regressions)}")
    print("OK test_no_regression")


def test_schema_compat() -> None:
    """Session with history saves and loads correctly."""
    with tempfile.TemporaryDirectory() as td:
        ctx = new_context("test", td, 604800)
        upsert_decision(ctx, key="test:compat", value="old", source="agent")
        upsert_decision(ctx, key="test:compat", value="new", source="agent")

        path = Path(td) / "session_context.v1.json"
        save_context_atomic(path, ctx)

        from src.session.context_store import load_context
        loaded = load_context(path)
        d = [x for x in loaded["ephemeral_decisions"] if x["key"] == "test:compat"][0]
        _assert(len(d.get("history", [])) == 1, "history should survive save/load")
    print("OK test_schema_compat")


def main() -> int:
    test_history_tracking()
    test_duplicate_suppression()
    test_history_cap()
    test_regression_detection()
    test_no_regression()
    test_schema_compat()
    print(json.dumps({"status": "OK", "tests_passed": 6}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
