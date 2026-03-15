"""Contract tests for context enrichment module."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Hot Files
# ---------------------------------------------------------------------------

def test_hot_files_returns_list() -> None:
    from src.session.context_enrichment import compute_hot_files
    result = compute_hot_files(repo_root=REPO_ROOT, days=30, top_n=10)
    assert isinstance(result, list)
    # In a git repo with commits, we should get results
    if result:
        assert "path" in result[0]
        assert "change_count" in result[0]
        assert result[0]["change_count"] >= 1


def test_hot_files_respects_top_n() -> None:
    from src.session.context_enrichment import compute_hot_files
    result = compute_hot_files(repo_root=REPO_ROOT, days=30, top_n=3)
    assert len(result) <= 3


def test_hot_files_sorted_by_frequency() -> None:
    from src.session.context_enrichment import compute_hot_files
    result = compute_hot_files(repo_root=REPO_ROOT, days=30, top_n=20)
    if len(result) >= 2:
        assert result[0]["change_count"] >= result[1]["change_count"]


# ---------------------------------------------------------------------------
# Hot Tests
# ---------------------------------------------------------------------------

def test_hot_tests_returns_test_files_only() -> None:
    from src.session.context_enrichment import compute_hot_tests
    result = compute_hot_tests(repo_root=REPO_ROOT, days=30, top_n=10)
    assert isinstance(result, list)
    for item in result:
        path = item["path"].lower()
        assert any(
            p in path for p in ["test_", "_test.", ".test.", ".spec.", "test.java", "tests.java"]
        ), f"{item['path']} is not a test file"


# ---------------------------------------------------------------------------
# Import Graph
# ---------------------------------------------------------------------------

def test_import_graph_scans_python_files() -> None:
    from src.session.context_enrichment import compute_import_graph
    graph = compute_import_graph(repo_root=REPO_ROOT, max_files=100)
    assert isinstance(graph, dict)
    # We have Python files in src/
    py_files = [k for k in graph if k.endswith(".py")]
    assert len(py_files) > 0


def test_import_graph_extracts_imports() -> None:
    from src.session.context_enrichment import compute_import_graph
    graph = compute_import_graph(repo_root=REPO_ROOT, max_files=200)
    # At least some files should have imports
    files_with_imports = {k: v for k, v in graph.items() if v}
    assert len(files_with_imports) > 0


def test_import_graph_respects_max_files() -> None:
    from src.session.context_enrichment import compute_import_graph
    graph = compute_import_graph(repo_root=REPO_ROOT, max_files=5)
    assert len(graph) <= 5


# ---------------------------------------------------------------------------
# Neighbors
# ---------------------------------------------------------------------------

def test_neighbors_finds_connected_files() -> None:
    from src.session.context_enrichment import compute_import_graph, compute_neighbors
    graph = compute_import_graph(repo_root=REPO_ROOT, max_files=200)
    if graph:
        target = list(graph.keys())[:1]
        neighbors = compute_neighbors(import_graph=graph, target_files=target, depth=1)
        assert isinstance(neighbors, list)


# ---------------------------------------------------------------------------
# File Ownership
# ---------------------------------------------------------------------------

def test_file_ownership_returns_authors() -> None:
    from src.session.context_enrichment import compute_file_ownership
    result = compute_file_ownership(repo_root=REPO_ROOT, top_n=5)
    assert isinstance(result, list)
    if result:
        assert "path" in result[0]
        assert "dominant_author" in result[0]


# ---------------------------------------------------------------------------
# Full Report
# ---------------------------------------------------------------------------

def test_full_enrichment_report() -> None:
    from src.session.context_enrichment import build_context_enrichment_report
    report = build_context_enrichment_report(repo_root=REPO_ROOT, days=30, top_n=10)
    assert report["version"] == "v1"
    assert report["kind"] == "context-enrichment-report"
    assert report["status"] == "OK"
    assert "hot_files" in report
    assert "hot_tests" in report
    assert "import_graph_summary" in report
    assert "hot_file_neighbors" in report
    assert "file_ownership" in report
    assert report["import_graph_summary"]["total_files_scanned"] >= 0


def test_report_on_non_git_dir() -> None:
    from src.session.context_enrichment import build_context_enrichment_report
    with tempfile.TemporaryDirectory() as tmp:
        report = build_context_enrichment_report(repo_root=Path(tmp), days=7, top_n=5)
        assert report["status"] == "OK"
        assert report["hot_files"] == []


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_schema_exists() -> None:
    path = REPO_ROOT / "schemas" / "context-enrichment-report.schema.v1.json"
    assert path.exists()
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema["title"] == "Context Enrichment Report"
