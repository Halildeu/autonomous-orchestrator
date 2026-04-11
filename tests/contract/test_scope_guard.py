"""Contract tests for scope guard (Phase 3).

Validates:
  - Scope initialization
  - WITHIN_SCOPE for normal writes
  - WARN when file count exceeds 2x declared
  - BLOCK when file count exceeds 3x declared
  - WARN on domain change
  - Scope expansion
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("src.ops.scope_guard", reason="scope_guard not yet implemented")

from src.ops.scope_guard import init_scope, check_scope, expand_scope, get_scope_summary


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    return ws


class TestScopeInit:
    def test_init_returns_v1(self, workspace: Path) -> None:
        state = init_scope(workspace, max_files=5)
        assert state["version"] == "v1"
        assert state["status"] == "WITHIN_SCOPE"
        assert state["declared_scope"]["max_files"] == 5

    def test_init_with_declared_files(self, workspace: Path) -> None:
        state = init_scope(workspace, declared_files=["a.py", "b.py"], max_files=3)
        assert state["declared_scope"]["files"] == ["a.py", "b.py"]


class TestScopeCheck:
    def test_within_scope(self, workspace: Path) -> None:
        init_scope(workspace, max_files=5)
        r = check_scope(workspace, new_file="a.py")
        assert r["status"] == "WITHIN_SCOPE"
        assert r["files_written"] == 1

    def test_auto_init(self, workspace: Path) -> None:
        # No init_scope called — auto-inits on first check
        r = check_scope(workspace, new_file="a.py")
        assert r["status"] == "WITHIN_SCOPE"

    def test_warn_on_2x(self, workspace: Path) -> None:
        init_scope(workspace, max_files=2)
        for i in range(5):
            r = check_scope(workspace, new_file=f"file_{i}.py")
        assert r["status"] == "WARN"

    def test_block_on_3x(self, workspace: Path) -> None:
        init_scope(workspace, max_files=2)
        for i in range(7):
            r = check_scope(workspace, new_file=f"file_{i}.py")
        assert r["status"] == "BLOCK"

    def test_domain_change_warn(self, workspace: Path) -> None:
        init_scope(workspace, declared_domains=["backend"], max_files=20)
        r = check_scope(workspace, new_file="Home.tsx", new_domain="frontend")
        assert r["status"] == "WARN"
        assert r["warnings_count"] >= 1

    def test_same_domain_no_warn(self, workspace: Path) -> None:
        init_scope(workspace, declared_domains=["backend"], max_files=20)
        r = check_scope(workspace, new_file="foo.py", new_domain="backend")
        assert r["status"] == "WITHIN_SCOPE"

    def test_dedup_files(self, workspace: Path) -> None:
        init_scope(workspace, max_files=5)
        check_scope(workspace, new_file="a.py")
        check_scope(workspace, new_file="a.py")  # Same file again
        r = check_scope(workspace, new_file="a.py")
        assert r["files_written"] == 1  # Not counted 3 times


class TestScopeExpand:
    def test_expand_increases_max(self, workspace: Path) -> None:
        init_scope(workspace, max_files=3)
        r = expand_scope(workspace, reason="User approved", additional_files=5)
        assert r["status"] == "EXPANDED"
        assert r["new_max_files"] == 8

    def test_expand_resets_block(self, workspace: Path) -> None:
        init_scope(workspace, max_files=2)
        for i in range(7):
            check_scope(workspace, new_file=f"f_{i}.py")
        expand_scope(workspace, reason="approved", additional_files=10)
        summary = get_scope_summary(workspace)
        assert summary["status"] == "WITHIN_SCOPE"


class TestScopeSummary:
    def test_summary_structure(self, workspace: Path) -> None:
        init_scope(workspace, max_files=5)
        check_scope(workspace, new_file="a.py")
        s = get_scope_summary(workspace)
        assert s["files_written"] == 1
        assert s["max_files"] == 5
        assert s["files_remaining"] == 4
        assert s["status"] == "WITHIN_SCOPE"

    def test_no_scope_returns_uninitialized(self, workspace: Path) -> None:
        s = get_scope_summary(workspace)
        assert s["status"] == "NO_SCOPE"
