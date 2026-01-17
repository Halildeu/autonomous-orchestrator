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


def _write_autopilot_override(ws: Path) -> None:
    path = ws / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json"
    payload = {
        "version": "v1",
        "defaults": {"selected_default": False, "max_apply_per_tick": 2},
        "selection_rules": [
            {
                "id": "ticket_manual_doc_only_safe",
                "when": {
                    "bucket": "TICKET",
                    "source_type": "MANUAL_REQUEST",
                    "impact_scope": "doc-only",
                    "kind_in": ["note", "doc-fix"],
                },
                "set": {
                    "autopilot_allowed": True,
                    "autopilot_reason": "DOC_ONLY_MANUAL",
                },
            }
        ],
    }
    _write_json(path, payload)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.doer_actionability import run_doer_actionability
    from src.ops.system_status_builder import _load_policy, build_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle
    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
    from src.ops.work_intake_from_sources import _intake_id, run_work_intake_build

    ws = repo_root / ".cache" / "ws_doer_surface_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    request_id = "REQ-DOER-SURFACE-1"
    _write_manual_request(ws, request_id)
    _write_autopilot_override(ws)

    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")
    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )
    run_work_intake_build(workspace_root=ws)

    actionability = run_doer_actionability(workspace_root=ws, out="auto")
    if actionability.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_surface_contract_test failed: actionability status")

    exec_result = run_work_intake_exec_ticket(workspace_root=ws, limit=1)
    if exec_result.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("doer_surface_contract_test failed: exec status")

    run_report_path = ws / ".cache" / "reports" / "airunner_run.v1.json"
    _write_json(
        run_report_path,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws),
            "doer_counts": {
                "applied": int(exec_result.get("applied_count") or 0),
                "planned": int(exec_result.get("planned_count") or 0),
                "skipped": int(exec_result.get("skipped_count") or 0),
                "skipped_by_reason": exec_result.get("skipped_by_reason") or {},
            },
        },
    )

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    doer_section = sections.get("doer") if isinstance(sections.get("doer"), dict) else None
    if not isinstance(doer_section, dict):
        raise SystemExit("doer_surface_contract_test failed: doer section missing")
    if not isinstance(doer_section.get("last_actionability_path"), str):
        raise SystemExit("doer_surface_contract_test failed: last_actionability_path missing")
    if not isinstance(doer_section.get("last_exec_report_path"), str):
        raise SystemExit("doer_surface_contract_test failed: last_exec_report_path missing")
    if not isinstance(doer_section.get("last_run_path"), str):
        raise SystemExit("doer_surface_contract_test failed: last_run_path missing")
    if not isinstance(doer_section.get("last_counts"), dict):
        raise SystemExit("doer_surface_contract_test failed: last_counts missing")

    report_path = ws / ".cache" / "reports" / "system_status.v1.json"
    _write_json(report_path, system_status)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=ws)
    if not isinstance(ui_snapshot.get("doer_summary"), dict):
        raise SystemExit("doer_surface_contract_test failed: doer_summary missing")
    if not isinstance(ui_snapshot.get("doer_last_exec_report_path"), str):
        raise SystemExit("doer_surface_contract_test failed: doer_last_exec_report_path missing")


if __name__ == "__main__":
    main()
