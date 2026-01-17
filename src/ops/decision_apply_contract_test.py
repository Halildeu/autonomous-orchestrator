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

    from src.ops.decision_inbox import run_decision_inbox_build, run_decision_apply

    ws = repo_root / ".cache" / "ws_decision_apply_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    exec_report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "entries": [
            {
                "intake_id": "INTAKE-DECISION-2",
                "bucket": "TICKET",
                "status": "SKIPPED",
                "skip_reason": "DECISION_NEEDED",
                "autopilot_reason": "DECISION_NEEDED",
                "evidence_paths": [],
            }
        ],
    }
    _write_json(ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json", exec_report)

    res = run_decision_inbox_build(workspace_root=ws)
    if res.get("status") != "OK":
        raise SystemExit("decision_apply_contract_test failed: decision inbox build not OK")

    inbox = json.loads((ws / ".cache" / "index" / "decision_inbox.v1.json").read_text(encoding="utf-8"))
    items = inbox.get("items") if isinstance(inbox, dict) else []
    if not items:
        raise SystemExit("decision_apply_contract_test failed: decision inbox empty")
    decision_id = items[0].get("decision_id")
    if not decision_id:
        raise SystemExit("decision_apply_contract_test failed: decision_id missing")

    apply_res = run_decision_apply(workspace_root=ws, decision_id=decision_id, option_id="B")
    if apply_res.get("status") != "OK":
        raise SystemExit("decision_apply_contract_test failed: apply status not OK")

    applied_path = ws / ".cache" / "index" / "decisions_applied.v1.jsonl"
    if not applied_path.exists():
        raise SystemExit("decision_apply_contract_test failed: decisions_applied missing")

    selection_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    if not selection_path.exists():
        raise SystemExit("decision_apply_contract_test failed: selection file missing")

    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_ids = selection.get("selected_ids") if isinstance(selection, dict) else []
    if "INTAKE-DECISION-2" not in selected_ids:
        raise SystemExit("decision_apply_contract_test failed: intake_id not selected after apply")


if __name__ == "__main__":
    main()
