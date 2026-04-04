"""Contract tests for memory sweep automation."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from scripts.memory_sweep import run_sweep, _smart_archive_candidates


@pytest.fixture()
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory"
    d.mkdir()
    # Create index
    (d / "MEMORY.md").write_text("# Memory\n## Project — Active\n- [A](project_a.md) — active\n", encoding="utf-8")
    (d / "project_a.md").write_text("---\nname: a\ntype: project\n---\nActive project", encoding="utf-8")
    return d


class TestRunSweep:
    def test_lightweight_fast(self, memory_dir: Path) -> None:
        r = run_sweep(memory_dir=memory_dir, lightweight=True, trigger="compaction")
        assert r["version"] == "v1"
        assert r["lightweight"] is True
        assert "index_sync" in r
        assert "stale_projects" in r
        assert "archive_candidates" not in r  # lightweight skips this

    def test_full_sweep(self, memory_dir: Path) -> None:
        r = run_sweep(memory_dir=memory_dir, lightweight=False, trigger="merge")
        assert r["lightweight"] is False
        assert "archive_candidates" in r
        assert "summary" in r
        assert r["summary"]["total_files"] >= 1

    def test_index_sync_detects_orphan(self, memory_dir: Path) -> None:
        (memory_dir / "orphan.md").write_text("---\nname: orphan\ntype: project\n---\nOrphan", encoding="utf-8")
        r = run_sweep(memory_dir=memory_dir, lightweight=False, trigger="manual")
        assert "orphan.md" in r["index_sync"]["orphaned_files"]
        assert r["index_sync"]["in_sync"] is False


class TestSmartArchive:
    def test_archives_done_and_old(self, memory_dir: Path) -> None:
        f = memory_dir / "project_done.md"
        f.write_text("---\nname: done\ntype: project\n---\nALL DONE. PR merged.", encoding="utf-8")
        old_time = time.time() - (10 * 86400)  # 10 days ago
        os.utime(f, (old_time, old_time))

        candidates = _smart_archive_candidates(memory_dir)
        assert len(candidates) == 1
        assert candidates[0]["filename"] == "project_done.md"

    def test_keeps_recent_done(self, memory_dir: Path) -> None:
        f = memory_dir / "project_just_done.md"
        f.write_text("---\nname: just_done\ntype: project\n---\nALL DONE today.", encoding="utf-8")
        # mtime is now (recent) — should NOT archive
        candidates = _smart_archive_candidates(memory_dir)
        assert len(candidates) == 0

    def test_keeps_active(self, memory_dir: Path) -> None:
        f = memory_dir / "project_active.md"
        f.write_text("---\nname: active\ntype: project\n---\nPhase 2 in progress", encoding="utf-8")
        old_time = time.time() - (10 * 86400)
        os.utime(f, (old_time, old_time))
        # No done indicators — should NOT archive
        candidates = _smart_archive_candidates(memory_dir)
        assert len(candidates) == 0

    def test_skips_already_archived(self, memory_dir: Path) -> None:
        f = memory_dir / "project_old_archived.md"
        f.write_text("---\nname: old\ntype: project\n---\n[ARCHIVED] ALL DONE", encoding="utf-8")
        old_time = time.time() - (60 * 86400)
        os.utime(f, (old_time, old_time))
        candidates = _smart_archive_candidates(memory_dir)
        assert len(candidates) == 0
