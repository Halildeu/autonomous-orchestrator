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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_closed_gap_filter"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    gap_register = {
        "version": "v1",
        "generated_at": "2026-03-08T00:00:00Z",
        "gaps": [
            {
                "id": "GAP-OPEN-001",
                "control_id": "OPEN-001",
                "severity": "medium",
                "risk_class": "medium",
                "effort": "medium",
                "status": "open",
                "notes": "Assessment not yet completed.",
            },
            {
                "id": "GAP-CLOSED-001",
                "control_id": "CLOSED-001",
                "severity": "medium",
                "risk_class": "medium",
                "effort": "medium",
                "status": "closed",
                "notes": "Closed via work_intake: WORK_ITEM_STATE_CLOSED.",
            },
        ],
    }
    _write_json(ws / ".cache" / "index" / "gap_register.v1.json", gap_register)

    result = run_work_intake_build(workspace_root=ws)
    if result.get("status") not in {"OK", "WARN"}:
        raise SystemExit("work_intake_closed_gap_filter_contract_test failed: build status")

    intake_obj = json.loads((ws / ".cache" / "index" / "work_intake.v1.json").read_text(encoding="utf-8"))
    items = intake_obj.get("items") if isinstance(intake_obj, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_closed_gap_filter_contract_test failed: items missing")
    source_refs = {str(item.get("source_ref") or "") for item in items if isinstance(item, dict)}
    if "GAP-OPEN-001" not in source_refs:
        raise SystemExit("work_intake_closed_gap_filter_contract_test failed: open gap missing from intake")
    if "GAP-CLOSED-001" in source_refs:
        raise SystemExit("work_intake_closed_gap_filter_contract_test failed: closed gap should be filtered")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
