"""Contract test for P4: Sliding Window Compaction."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.session.context_store import new_context, save_context_atomic, upsert_decision
from src.session.compaction_engine import compact_session_decisions, should_compact


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {msg}")
        raise SystemExit(2)


def test_below_threshold() -> None:
    """5 decisions, threshold 30 → no compaction."""
    ctx = new_context("test", "/tmp", 604800)
    for i in range(5):
        upsert_decision(ctx, key=f"key:{i}", value=f"val{i}", source="agent")

    policy = {"trigger_threshold": 30, "keep_recent_count": 10}
    _assert(not should_compact(ctx, policy=policy), "should not compact below threshold")

    result = compact_session_decisions(ctx, policy=policy)
    _assert(not result["compacted"], "expected no compaction")
    print("OK test_below_threshold")


def test_compact_keeps_recent() -> None:
    """30 decisions, keep 10 → 10 kept, 20 archived."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("test", str(ws), 604800)
        for i in range(30):
            upsert_decision(ctx, key=f"key:{i:03d}", value=f"val{i}", source="agent")

        policy = {"trigger_threshold": 30, "keep_recent_count": 10, "archive_older": True, "enabled": True}
        _assert(should_compact(ctx, policy=policy), "should compact at threshold")

        result = compact_session_decisions(ctx, policy=policy, workspace_root=ws, session_id="test")
        _assert(result["compacted"], "expected compaction")
        _assert(result["kept"] == 10, f"expected 10 kept, got {result['kept']}")
        _assert(result["archived"] == 20, f"expected 20 archived, got {result['archived']}")
        _assert(len(ctx["ephemeral_decisions"]) == 10, f"expected 10 decisions left, got {len(ctx['ephemeral_decisions'])}")
    print("OK test_compact_keeps_recent")


def test_archive_file_created() -> None:
    """Archive file is created in compaction_archive directory."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("test", str(ws), 604800)
        for i in range(20):
            upsert_decision(ctx, key=f"key:{i}", value=f"val{i}", source="agent")

        policy = {"trigger_threshold": 15, "keep_recent_count": 5, "archive_older": True, "enabled": True}
        result = compact_session_decisions(ctx, policy=policy, workspace_root=ws, session_id="test")

        archive_dir = ws / ".cache" / "sessions" / "test" / "compaction_archive"
        _assert(archive_dir.exists(), "archive directory should exist")
        archives = list(archive_dir.glob("*.v1.json"))
        _assert(len(archives) == 1, f"expected 1 archive file, got {len(archives)}")

        data = json.loads(archives[0].read_text())
        _assert(data["decisions_archived"] == 15, f"expected 15 archived, got {data['decisions_archived']}")
    print("OK test_archive_file_created")


def test_compaction_metadata_updated() -> None:
    """Compaction status and trigger recorded in context."""
    ctx = new_context("test", "/tmp", 604800)
    for i in range(20):
        upsert_decision(ctx, key=f"key:{i}", value=f"val{i}", source="agent")

    policy = {"trigger_threshold": 15, "keep_recent_count": 5, "enabled": True}
    compact_session_decisions(ctx, policy=policy)

    _assert(ctx["compaction"]["status"] == "completed", "compaction status should be completed")
    _assert(ctx["compaction"]["source"] == "sliding_window", "compaction source should be sliding_window")
    _assert(ctx["compaction"]["trigger"] == "decision_count", "compaction trigger should be decision_count")
    print("OK test_compaction_metadata_updated")


def test_save_load_after_compaction() -> None:
    """Compacted context saves and loads correctly."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        ctx = new_context("test", str(ws), 604800)
        for i in range(20):
            upsert_decision(ctx, key=f"key:{i}", value=f"val{i}", source="agent")

        policy = {"trigger_threshold": 15, "keep_recent_count": 5, "enabled": True}
        compact_session_decisions(ctx, policy=policy, workspace_root=ws)

        path = ws / "session_context.v1.json"
        save_context_atomic(path, ctx)

        from src.session.context_store import load_context
        loaded = load_context(path)
        _assert(len(loaded["ephemeral_decisions"]) == 5, "5 decisions should survive save/load after compaction")
    print("OK test_save_load_after_compaction")


def main() -> int:
    test_below_threshold()
    test_compact_keeps_recent()
    test_archive_file_created()
    test_compaction_metadata_updated()
    test_save_load_after_compaction()
    print(json.dumps({"status": "OK", "tests_passed": 5}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
