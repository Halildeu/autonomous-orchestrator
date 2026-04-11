"""Contract tests for memory frontmatter parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("src.shared.memory_parser", reason="memory_parser not yet implemented")

from src.shared.memory_parser import (
    parse_memory_file,
    list_memory_files,
    parse_memory_index,
    find_orphaned_files,
    detect_stale_projects,
)


@pytest.fixture()
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory"
    d.mkdir()
    return d


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestParseMemoryFile:
    def test_parses_frontmatter(self, memory_dir: Path) -> None:
        _write(memory_dir / "test.md", "---\nname: test_name\ndescription: test desc\ntype: project\n---\n\nBody content here.")
        r = parse_memory_file(memory_dir / "test.md")
        assert r["name"] == "test_name"
        assert r["description"] == "test desc"
        assert r["type"] == "project"
        assert "Body content" in r["body"]

    def test_no_frontmatter(self, memory_dir: Path) -> None:
        _write(memory_dir / "plain.md", "Just plain text")
        r = parse_memory_file(memory_dir / "plain.md")
        assert r["body"] == "Just plain text"
        assert r["name"] == ""

    def test_file_not_found(self, memory_dir: Path) -> None:
        r = parse_memory_file(memory_dir / "missing.md")
        assert r["error"] == "file_not_found"


class TestListMemoryFiles:
    def test_lists_all_except_index(self, memory_dir: Path) -> None:
        _write(memory_dir / "MEMORY.md", "# Index")
        _write(memory_dir / "a.md", "---\nname: a\ntype: user\n---\nA")
        _write(memory_dir / "b.md", "---\nname: b\ntype: feedback\n---\nB")
        files = list_memory_files(memory_dir)
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert names == {"a", "b"}

    def test_empty_dir(self, memory_dir: Path) -> None:
        assert list_memory_files(memory_dir) == []


class TestParseMemoryIndex:
    def test_parses_entries(self, memory_dir: Path) -> None:
        _write(memory_dir / "MEMORY.md", "# Memory\n## User\n- [Profile](user_profile.md) — desc\n## Feedback\n- [Rule](feedback_rule.md) — desc2\n")
        entries = parse_memory_index(memory_dir)
        assert len(entries) == 2
        assert entries[0]["filename"] == "user_profile.md"
        assert entries[0]["category"] == "User"
        assert entries[1]["category"] == "Feedback"


class TestFindOrphaned:
    def test_detects_orphaned(self, memory_dir: Path) -> None:
        _write(memory_dir / "MEMORY.md", "## User\n- [A](a.md) — desc\n")
        _write(memory_dir / "a.md", "content")
        _write(memory_dir / "orphan.md", "content")
        orphaned, missing = find_orphaned_files(memory_dir)
        assert "orphan.md" in orphaned
        assert missing == []

    def test_detects_missing(self, memory_dir: Path) -> None:
        _write(memory_dir / "MEMORY.md", "## User\n- [A](a.md) — desc\n- [B](b.md) — desc\n")
        _write(memory_dir / "a.md", "content")
        orphaned, missing = find_orphaned_files(memory_dir)
        assert orphaned == []
        assert "b.md" in missing


class TestStaleDetection:
    def test_detects_stale(self, memory_dir: Path) -> None:
        import os, time
        f = memory_dir / "project_old.md"
        _write(f, "---\nname: old\ntype: project\n---\nOld project")
        # Set mtime to 60 days ago
        old_time = time.time() - (60 * 86400)
        os.utime(f, (old_time, old_time))

        stale = detect_stale_projects(memory_dir, stale_days=30)
        assert len(stale) == 1
        assert stale[0]["filename"] == "project_old.md"

    def test_skips_archived(self, memory_dir: Path) -> None:
        import os, time
        f = memory_dir / "project_done.md"
        _write(f, "---\nname: done\ntype: project\n---\n[ARCHIVED] Done")
        old_time = time.time() - (60 * 86400)
        os.utime(f, (old_time, old_time))

        stale = detect_stale_projects(memory_dir, stale_days=30)
        assert len(stale) == 0

    def test_fresh_not_stale(self, memory_dir: Path) -> None:
        _write(memory_dir / "project_new.md", "---\nname: new\ntype: project\n---\nNew")
        stale = detect_stale_projects(memory_dir, stale_days=30)
        assert len(stale) == 0
