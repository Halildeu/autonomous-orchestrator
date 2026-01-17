from __future__ import annotations

import argparse
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

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import run_work_intake_build, _intake_id

    ws = repo_root / ".cache" / "ws_work_intake_exec_selected"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-TEST-EXEC-001"
    manual_request = {
        "version": "v1",
        "request_id": request_id,
        "received_at": _now_iso(),
        "source": {"type": "chat"},
        "text": "Doc note",
        "kind": "note",
        "impact_scope": "doc-only",
        "requires_core_change": False,
    }
    _write_json(ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json", manual_request)

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN"}:
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: build status")

    exec_res = run_work_intake_exec_ticket(workspace_root=ws, limit=3)
    if exec_res.get("status") != "IDLE" or exec_res.get("error_code") != "NO_SELECTED_AUTOPILOT_ITEMS":
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: expected IDLE with no selection")

    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")
    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )

    res2 = run_work_intake_build(workspace_root=ws)
    if res2.get("status") not in {"OK", "WARN"}:
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: rebuild status")

    exec_res2 = run_work_intake_exec_ticket(workspace_root=ws, limit=3)
    if int(exec_res2.get("applied_count") or 0) < 1:
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: expected applied>=1")

    report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    applied_entries = [e for e in entries if isinstance(e, dict) and e.get("status") == "APPLIED"]
    if not applied_entries:
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: applied entries missing")
    evidence = applied_entries[0].get("evidence_paths")
    if not isinstance(evidence, list) or not evidence:
        raise SystemExit("work_intake_exec_selected_only_contract_test failed: evidence_paths missing")


if __name__ == "__main__":
    main()
