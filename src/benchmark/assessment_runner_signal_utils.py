from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.benchmark.docs_drift_utils import DOCS_DRIFT_EXCLUDE_DIRS, _iter_md_paths


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_doc_nav_signal(*, workspace_root: Path) -> dict[str, Any]:
    strict_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    summary_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    report_path = strict_path if strict_path.exists() else summary_path
    if not report_path.exists():
        return {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0, "report_path": ""}
    try:
        obj = _load_json(report_path)
    except Exception:
        return {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0, "report_path": str(report_path)}
    counts = obj.get("counts") if isinstance(obj, dict) else None
    if isinstance(counts, dict):
        placeholders = int(counts.get("placeholder_refs_count", 0) or 0)
        broken_refs = int(counts.get("broken_refs", 0) or 0)
        orphan_critical = int(counts.get("orphan_critical", 0) or 0)
    else:
        placeholders = int(obj.get("placeholder_refs_count", 0) or 0) if isinstance(obj, dict) else 0
        broken_refs = int(obj.get("broken_refs", 0) or 0) if isinstance(obj, dict) else 0
        orphan_critical = int(obj.get("orphan_critical", 0) or 0) if isinstance(obj, dict) else 0
    return {
        "placeholders_count": placeholders,
        "broken_refs": broken_refs,
        "orphan_critical": orphan_critical,
        "report_path": str(report_path),
    }


def _load_docs_hygiene_signal(*, core_root: Path) -> dict[str, Any]:
    repo_root = core_root
    ops_root = repo_root / "docs" / "OPERATIONS"
    ops_files = _iter_md_paths(ops_root, exclude_dirs=set())
    docs_ops_md_count = len(ops_files)
    docs_ops_md_bytes = sum(p.stat().st_size for p in ops_files)
    repo_files = _iter_md_paths(repo_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS)
    repo_md_total_count = len(repo_files)
    return {
        "docs_ops_md_count": int(docs_ops_md_count),
        "docs_ops_md_bytes": int(docs_ops_md_bytes),
        "repo_md_total_count": int(repo_md_total_count),
    }
