"""Contract tests for code-aware index."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_index_returns_structure() -> None:
    from src.session.code_aware_index import build_code_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=50)
    assert index["version"] == "v1"
    assert index["kind"] == "code-aware-index"
    assert index["status"] == "OK"
    assert index["summary"]["total_files"] > 0
    assert index["summary"]["total_files"] <= 50


def test_index_extracts_python_symbols() -> None:
    from src.session.code_aware_index import build_code_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=200)
    py_entries = [e for e in index["entries"] if e["suffix"] == ".py" and e.get("symbols")]
    assert len(py_entries) > 0
    # Should find some known functions
    all_symbols = []
    for e in py_entries:
        all_symbols.extend(e.get("symbols", []))
    # Our codebase should have at least some recognizable symbols
    assert len(all_symbols) > 10


def test_index_assigns_domains() -> None:
    from src.session.code_aware_index import build_code_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=200)
    domains = index["summary"]["domains"]
    assert isinstance(domains, dict)
    assert len(domains) > 0
    # We should have at least core and ci
    assert sum(domains.values()) == index["summary"]["total_files"]


def test_write_and_load_roundtrip() -> None:
    from src.session.code_aware_index import build_code_index, write_code_index, load_code_index
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        index = build_code_index(repo_root=REPO_ROOT, max_files=10)
        rel = write_code_index(repo_root=tmp_root, index=index)
        assert (tmp_root / rel).exists()
        loaded = load_code_index(repo_root=tmp_root)
        assert loaded is not None
        assert loaded["summary"]["total_files"] == index["summary"]["total_files"]


def test_load_returns_none_on_missing() -> None:
    from src.session.code_aware_index import load_code_index
    with tempfile.TemporaryDirectory() as tmp:
        assert load_code_index(repo_root=Path(tmp)) is None


def test_search_by_symbol() -> None:
    from src.session.code_aware_index import build_code_index, search_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=500)
    # Search for any symbol that should be in the index
    # Use a symbol from early-alphabetical src/ files
    all_symbols = []
    for e in index["entries"]:
        all_symbols.extend(e.get("symbols", []))
    assert len(all_symbols) > 0
    # Search for first found symbol
    target = all_symbols[0]
    results = search_index(index=index, query=target)
    assert len(results) > 0


def test_search_by_path() -> None:
    from src.session.code_aware_index import build_code_index, search_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=500)
    # Search for "store" which appears in early src/ files
    results = search_index(index=index, query="store")
    assert len(results) > 0


def test_search_with_domain_filter() -> None:
    from src.session.code_aware_index import build_code_index, search_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=200)
    all_results = search_index(index=index, query="check")
    ci_results = search_index(index=index, query="check", domain_filter="ci")
    assert len(ci_results) <= len(all_results)
    for r in ci_results:
        assert r["domain"] == "ci"


def test_search_empty_query_returns_nothing() -> None:
    from src.session.code_aware_index import build_code_index, search_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=50)
    assert search_index(index=index, query="") == []


def test_search_respects_max_results() -> None:
    from src.session.code_aware_index import build_code_index, search_index
    index = build_code_index(repo_root=REPO_ROOT, max_files=200)
    results = search_index(index=index, query="test", max_results=3)
    assert len(results) <= 3
