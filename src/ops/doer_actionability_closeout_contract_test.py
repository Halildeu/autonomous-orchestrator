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


def _write_manual_request(ws: Path, request_id: str) -> None:
    _write_json(
        ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
        {
            "version": "v1",
            "request_id": request_id,
            "received_at": _now_iso(),
            "source": {"type": "chat"},
            "text": "Doc note",
            "kind": "note",
            "impact_scope": "doc-only",
            "requires_core_change": False,
        },
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_doer_section(report: dict) -> dict | None:
    sections = report.get("sections") if isinstance(report.get("sections"), dict) else {}
    if not isinstance(sections, dict):
        return None
    doer = sections.get("doer") if isinstance(sections.get("doer"), dict) else None
    return doer if isinstance(doer, dict) else None


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.doer_actionability import run_doer_actionability
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import _intake_id
    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_doer_actionability_closeout_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-DOER-CLOSEOUT-1"
    _write_manual_request(ws, request_id)
    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")

    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )

    actionability = run_doer_actionability(workspace_root=ws, out="auto")
    if actionability.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_actionability_closeout_contract_test failed: actionability status")
    actionability_report = ws / ".cache" / "reports" / "doer_actionability.v1.json"
    if not actionability_report.exists():
        raise SystemExit("doer_actionability_closeout_contract_test failed: actionability report missing")
    actionability_obj = _load_json(actionability_report)
    counts = actionability_obj.get("counts") if isinstance(actionability_obj.get("counts"), dict) else {}
    candidate_total = int(counts.get("candidate_total") or 0)

    exec_result = run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    if exec_result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_actionability_closeout_contract_test failed: exec status")
    exec_report = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    exec_obj = _load_json(exec_report)
    exec_selected = int(exec_obj.get("selected_count") or 0)
    if candidate_total != exec_selected:
        raise SystemExit("doer_actionability_closeout_contract_test failed: candidate_total mismatch")

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    doer_section = _resolve_doer_section(system_status)
    if not isinstance(doer_section, dict):
        raise SystemExit("doer_actionability_closeout_contract_test failed: doer section missing")
    if not isinstance(doer_section.get("last_exec_report_path"), str):
        raise SystemExit("doer_actionability_closeout_contract_test failed: last_exec_report_path missing")
    if not isinstance(doer_section.get("last_counts"), dict):
        raise SystemExit("doer_actionability_closeout_contract_test failed: last_counts missing")

    report_path = ws / ".cache" / "reports" / "system_status.v1.json"
    _write_json(report_path, system_status)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=ws)
    if not isinstance(ui_snapshot.get("doer_last_exec_report_path"), str):
        raise SystemExit("doer_actionability_closeout_contract_test failed: ui doer_last_exec_report_path missing")
    if not isinstance(ui_snapshot.get("doer_summary"), dict):
        raise SystemExit("doer_actionability_closeout_contract_test failed: ui doer_summary missing")


if __name__ == "__main__":
    main()
