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

    ws = repo_root / ".cache" / "ws_intake_budget_test"
    if ws.exists():
        shutil.rmtree(ws)

    budget_dir = ws / ".cache" / "script_budget"
    budget_dir.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "WARN",
        "exceeded_soft": [{"path": "src/ops/system_status_report.py", "lines": 999, "rule": "soft"}],
        "exceeded_hard": [],
    }
    _write_json(budget_dir / "report.json", report_payload)

    run_work_intake_build(workspace_root=ws)
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("Script budget test failed: work_intake.v1.json missing.")

    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise SystemExit("Script budget test failed: items must be a list.")

    target_ref = "src/ops/system_status_report.py"
    matched = [
        i
        for i in items
        if isinstance(i, dict)
        and i.get("source_type") == "SCRIPT_BUDGET"
        and i.get("source_ref") == target_ref
    ]
    if not matched:
        raise SystemExit("Script budget test failed: SCRIPT_BUDGET item missing.")
    item = matched[0]
    if item.get("bucket") != "PROJECT":
        raise SystemExit("Script budget test failed: SCRIPT_BUDGET must map to PROJECT.")
    if item.get("severity") != "S2" or item.get("priority") != "P2":
        raise SystemExit("Script budget test failed: SCRIPT_BUDGET must be S2/P2.")
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    if "M0" not in [str(t) for t in tags]:
        raise SystemExit("Script budget test failed: SCRIPT_BUDGET must include M0 tag.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
