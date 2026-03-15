"""Contract tests for context-aware search (context_scope filtering and boosting)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure sibling modules are importable
_MODULE_DIR = Path(__file__).resolve().parents[1]
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from search_adapter_query import _apply_context_scope


def _make_hit(path: str) -> dict[str, Any]:
    return {"path": path, "line": 1, "col": 0, "preview": "...", "score": None}


def test_no_context_scope_preserves_order() -> None:
    hits = [_make_hit("a.py"), _make_hit("b.py"), _make_hit("c.py")]
    result = _apply_context_scope(hits, [])
    # Empty scope set: no matches, all go to out_scope
    assert [h["path"] for h in result] == ["a.py", "b.py", "c.py"]


def test_context_scope_boosts_matching_hits() -> None:
    hits = [
        _make_hit("src/ops/manage.py"),
        _make_hit("docs/OPERATIONS/CODEX-UX.md"),
        _make_hit("schemas/policy.json"),
        _make_hit("roadmaps/SSOT/roadmap.v1.json"),
    ]
    result = _apply_context_scope(hits, ["roadmaps", "docs/OPERATIONS"])

    # Matching hits should come first
    assert result[0]["context_match"] is True
    assert result[1]["context_match"] is True
    # Non-matching after
    assert result[-1]["context_match"] is False


def test_context_match_flag_set() -> None:
    hits = [_make_hit("src/foo.py"), _make_hit("docs/bar.md")]
    result = _apply_context_scope(hits, ["docs"])
    for h in result:
        if "docs" in h["path"]:
            assert h["context_match"] is True
        else:
            assert h["context_match"] is False


def test_exact_path_match() -> None:
    hits = [_make_hit("AGENTS.md"), _make_hit("README.md")]
    result = _apply_context_scope(hits, ["AGENTS.md"])
    assert result[0]["path"] == "AGENTS.md"
    assert result[0]["context_match"] is True


def test_prefix_match() -> None:
    hits = [_make_hit("src/ops/drift.py"), _make_hit("ci/check.py")]
    result = _apply_context_scope(hits, ["src/ops"])
    assert result[0]["path"] == "src/ops/drift.py"
    assert result[0]["context_match"] is True
    assert result[1]["context_match"] is False
