from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_sections import _doc_graph_section

    ws = repo_root / ".cache" / "ws_system_status_doc_nav_placeholders_delta_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    report = {
        "version": "v1",
        "generated_at": "fixed",
        "repo_root": str(repo_root),
        "workspace_root": str(ws),
        "status": "OK",
        "counts": {
            "scanned_files": 0,
            "reference_count": 0,
            "broken_refs": 0,
            "orphan_critical": 0,
            "ambiguity": 0,
            "ambiguity_count": 0,
            "critical_nav_gaps": 0,
            "workspace_bound_refs_count": 0,
            "external_pointer_refs_count": 0,
            "placeholder_refs_count": 25,
            "archive_refs_count": 0,
        },
        "placeholders_baseline": 25,
        "placeholders_delta": 0,
        "placeholders_warn_mode": "delta",
        "broken_refs": [],
        "orphan_critical": [],
        "notes": [],
    }
    report_path = ws / ".cache" / "reports" / "doc_graph_report.v1.json"
    _write_json(report_path, report)

    section = _doc_graph_section(repo_root, ws, allow_write=False)
    if not isinstance(section, dict):
        raise SystemExit("system_status_doc_nav_placeholders_delta_contract_test failed: missing section")
    if section.get("placeholders_baseline") != 25:
        raise SystemExit("system_status_doc_nav_placeholders_delta_contract_test failed: baseline missing")
    if section.get("placeholders_delta") != 0:
        raise SystemExit("system_status_doc_nav_placeholders_delta_contract_test failed: delta missing")
    if section.get("placeholders_warn_mode") != "delta":
        raise SystemExit("system_status_doc_nav_placeholders_delta_contract_test failed: warn_mode missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
