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

    ws = repo_root / ".cache" / "ws_intake_regression_test"
    if ws.exists():
        shutil.rmtree(ws)

    index_dir = ws / ".cache" / "index"
    report_dir = ws / ".cache" / "reports"
    index_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    regression_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "regressions": [{"gap_id": "GAP-REG-INC", "severity": "high"}],
    }
    _write_json(index_dir / "regression_index.v1.json", regression_payload)

    pdca_payload = {"version": "v1", "generated_at": _now_iso(), "status": "OK", "notes": []}
    _write_json(report_dir / "pdca_recheck_report.v1.json", pdca_payload)

    run_work_intake_build(workspace_root=ws)
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("PDCA regression test failed: work_intake.v1.json missing.")

    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise SystemExit("PDCA regression test failed: items must be a list.")

    regression_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "PDCA_REGRESSION"]
    if not regression_items:
        raise SystemExit("PDCA regression test failed: PDCA_REGRESSION item missing.")
    for item in regression_items:
        if item.get("bucket") != "INCIDENT":
            raise SystemExit("PDCA regression test failed: PDCA_REGRESSION must map to INCIDENT.")
        if item.get("severity") != "S1" or item.get("priority") != "P1":
            raise SystemExit("PDCA regression test failed: PDCA_REGRESSION must be S1/P1.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
