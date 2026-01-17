from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_intake_doc_nav_test"
    if ws.exists():
        shutil.rmtree(ws)

    report_dir = ws / ".cache" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    doc_nav_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "FAIL",
        "counts": {
            "critical_nav_gaps": 2,
            "broken_refs": 0,
            "placeholder_refs_count": 0,
        },
    }
    _write_json(report_dir / "doc_graph_report.strict.v1.json", doc_nav_payload)

    run_work_intake_build(workspace_root=ws)
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("Doc nav test failed: work_intake.v1.json missing.")

    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise SystemExit("Doc nav test failed: items must be a list.")

    nav_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "DOC_NAV"]
    if not nav_items:
        raise SystemExit("Doc nav test failed: DOC_NAV item missing.")
    for item in nav_items:
        if item.get("bucket") != "INCIDENT":
            raise SystemExit("Doc nav test failed: DOC_NAV must map to INCIDENT.")
        if item.get("severity") != "S1" or item.get("priority") != "P1":
            raise SystemExit("Doc nav test failed: DOC_NAV must be S1/P1.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
