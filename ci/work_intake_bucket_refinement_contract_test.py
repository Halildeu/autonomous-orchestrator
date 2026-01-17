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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_intake_bucket_refinement_test"
    if ws.exists():
        shutil.rmtree(ws)

    index_dir = ws / ".cache" / "index"
    budget_dir = ws / ".cache" / "script_budget"
    index_dir.mkdir(parents=True, exist_ok=True)
    budget_dir.mkdir(parents=True, exist_ok=True)

    gap_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "gaps": [
            {
                "id": "GAP-COVERAGE-01",
                "control_id": "CTRL-COVERAGE",
                "metric_id": "METRIC-COVERAGE",
                "severity": "low",
                "risk_class": "low",
                "effort": "low",
                "report_only": False,
                "evidence_pointers": [".cache/index/assessment_raw.v1.json"],
            }
        ],
    }
    _write_json(index_dir / "gap_register.v1.json", gap_payload)

    script_budget_payload = {
        "version": "v1",
        "status": "WARN",
        "exceeded_soft": [{"path": "src/ops/example.py", "lines": 999, "rule": "soft"}],
        "exceeded_hard": [],
    }
    _write_json(budget_dir / "report.json", script_budget_payload)

    result = run_work_intake_build(workspace_root=ws)
    status = result.get("status") if isinstance(result, dict) else None
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Bucket refinement test failed: intake build status invalid.")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("Bucket refinement test failed: work_intake.v1.json missing.")

    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload.get("items"), list) else []

    gap_bucket = None
    budget_bucket = None
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("source_type") == "GAP" and item.get("source_ref") == "GAP-COVERAGE-01":
            gap_bucket = str(item.get("bucket"))
        if item.get("source_type") == "SCRIPT_BUDGET" and item.get("source_ref") == "src/ops/example.py":
            budget_bucket = str(item.get("bucket"))

    if gap_bucket != "TICKET":
        raise SystemExit(f"Bucket refinement test failed: GAP-COVERAGE-01 expected TICKET, got {gap_bucket}.")
    if budget_bucket != "PROJECT":
        raise SystemExit(f"Bucket refinement test failed: script budget expected PROJECT, got {budget_bucket}.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
