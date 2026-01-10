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


def _write_preflight_stamp(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws),
            "gates": {
                "validate_schemas": "PASS",
                "smoke_fast": "PASS",
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0, "status": "OK"},
            },
            "overall": "PASS",
            "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.commands.maintenance_cmds import cmd_work_intake_select
    from src.ops.work_intake_from_sources import _intake_id
    from src.prj_airunner.airunner_tick import run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_tick_selected"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "lock_ttl_seconds": 900,
            "heartbeat_interval_seconds": 300,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
            "watchdog": {"enabled": True, "heartbeat_stale_seconds": 1800, "max_recoveries_per_day": 3},
            "job_policy": {"max_running_jobs": 0, "poll_interval_seconds": 0, "closeout_ttl_days": 7, "keep_last_n": 50},
            "limits": {"max_ticks_per_run": 1, "max_actions_per_tick": 1, "max_plans_per_tick": 1},
            "single_gate": {
                "allowed_ops": [
                    "work-intake-check",
                    "work-intake-exec-ticket",
                    "system-status",
                    "portfolio-status",
                    "ui-snapshot-bundle",
                ],
                "require_strict_isolation": True,
            },
            "notes": ["PROGRAM_LED=true", "WORKSPACE_ONLY=true"],
        },
    )
    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json",
        {
            "version": "v1",
            "jobs": {
                "max_running": 0,
                "max_poll_per_tick": 0,
                "poll_interval_seconds": 0,
                "timeout_seconds": 60,
                "stale_after_seconds": 3600,
                "allowed_job_types": [],
                "network_required_job_types": [],
            },
            "perf": {
                "enable": False,
                "event_log_max_lines": 10,
                "time_sinks_window": 0,
                "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1},
            },
            "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
        },
    )

    request_id = "REQ-TEST-AIRRUNNER-SELECT"
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

    _write_preflight_stamp(ws)

    res = run_airunner_tick(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("airunner_tick_selected_only_contract_test failed: tick status")

    exec_report = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    report_obj = json.loads(exec_report.read_text(encoding="utf-8")) if exec_report.exists() else {}
    if report_obj.get("error_code") != "NO_SELECTED_AUTOPILOT_ITEMS":
        raise SystemExit("airunner_tick_selected_only_contract_test failed: expected no selection")

    intake_id = _intake_id("MANUAL_REQUEST", request_id, "TICKET")
    cmd_work_intake_select(
        argparse.Namespace(
            workspace_root=str(ws),
            intake_id=intake_id,
            selected="true",
        )
    )

    res2 = run_airunner_tick(workspace_root=ws)
    if res2.get("status") not in {"OK", "WARN"}:
        raise SystemExit("airrunner_tick_selected_only_contract_test failed: tick status after select")

    report_obj = json.loads(exec_report.read_text(encoding="utf-8"))
    if int(report_obj.get("applied_count") or 0) < 1:
        raise SystemExit("airrunner_tick_selected_only_contract_test failed: expected applied>=1")


if __name__ == "__main__":
    main()
