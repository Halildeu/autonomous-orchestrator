"""Contract test for Extension-Context Bridge."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.session.context_store import new_context, save_context_atomic
from src.ops.extension_context_bridge import (
    read_extension_decisions, write_extension_decision,
    get_context_for_extension, collect_extension_output_paths,
)

def _assert(cond, msg):
    if not cond: print(f"FAIL {msg}"); raise SystemExit(2)

def test_write_creates_prefixed_key():
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("default", str(ws), 604800)
        p = ws / ".cache/sessions/default/session_context.v1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p, ctx)

        result = write_extension_decision(workspace_root=ws, extension_id="PRJ-DEPLOY", key="status", value="OK")
        _assert(result["status"] == "OK", f"expected OK, got {result['status']}")
        _assert(result["key"] == "ext:PRJ-DEPLOY:status", f"wrong key: {result['key']}")
    print("OK test_write_creates_prefixed_key")

def test_read_returns_only_own_namespace():
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("default", str(ws), 604800)
        p = ws / ".cache/sessions/default/session_context.v1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p, ctx)

        write_extension_decision(workspace_root=ws, extension_id="PRJ-A", key="k1", value="v1")
        write_extension_decision(workspace_root=ws, extension_id="PRJ-B", key="k2", value="v2")

        a_decisions = read_extension_decisions(workspace_root=ws, extension_id="PRJ-A")
        _assert(len(a_decisions) == 1, f"PRJ-A should have 1 decision, got {len(a_decisions)}")
        _assert(a_decisions[0]["key"] == "ext:PRJ-A:k1", "wrong key")

        b_decisions = read_extension_decisions(workspace_root=ws, extension_id="PRJ-B")
        _assert(len(b_decisions) == 1, f"PRJ-B should have 1 decision, got {len(b_decisions)}")
    print("OK test_read_returns_only_own_namespace")

def test_context_summary():
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("default", str(ws), 604800)
        p = ws / ".cache/sessions/default/session_context.v1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        save_context_atomic(p, ctx)

        write_extension_decision(workspace_root=ws, extension_id="PRJ-X", key="test", value=42)
        summary = get_context_for_extension(workspace_root=ws, extension_id="PRJ-X")
        _assert(summary["extension_id"] == "PRJ-X", "wrong extension_id")
        _assert(len(summary["own_decisions"]) == 1, "should have 1 own decision")
    print("OK test_context_summary")

def test_no_session():
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        decisions = read_extension_decisions(workspace_root=ws, extension_id="PRJ-NONE")
        _assert(decisions == [], "should return empty list")
        result = write_extension_decision(workspace_root=ws, extension_id="PRJ-NONE", key="k", value="v")
        _assert(result["status"] == "SKIP", f"expected SKIP, got {result['status']}")
    print("OK test_no_session")

def test_collect_output_paths():
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        reg_path = ws / ".cache/index/extension_registry.v1.json"
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(json.dumps({
            "extensions": [
                {"extension_id": "A", "enabled": True, "outputs": {"workspace_reports": [".cache/reports/a.json"]}},
                {"extension_id": "B", "enabled": False, "outputs": {"workspace_reports": [".cache/reports/b.json"]}},
                {"extension_id": "C", "enabled": True, "outputs": {"workspace_reports": [".cache/reports/c.json"]}},
            ]
        }) + "\n")
        paths = collect_extension_output_paths(ws)
        _assert(len(paths) == 2, f"expected 2 (enabled only), got {len(paths)}")
        _assert(".cache/reports/a.json" in paths, "a.json missing")
        _assert(".cache/reports/b.json" not in paths, "b.json should be excluded (disabled)")
    print("OK test_collect_output_paths")

def main():
    test_write_creates_prefixed_key()
    test_read_returns_only_own_namespace()
    test_context_summary()
    test_no_session()
    test_collect_output_paths()
    print(json.dumps({"status": "OK", "tests_passed": 5}, sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
