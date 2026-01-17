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

    import src.prj_airunner.airunner_tick as airunner_tick_mod

    def _fast_gate_stub(_workspace_root: Path) -> dict:
        return {
            "validate_schemas": "PASS",
            "smoke_fast": "PASS",
            "script_budget": "PASS",
            "hard_exceeded": 0,
            "report_path": "",
        }

    airunner_tick_mod._run_fast_gate = _fast_gate_stub

    def _stub_ui_snapshot(args):
        report_path = Path(str(args.out))
        _write_json(report_path, {"status": "OK", "generated_at": _now_iso()})
        return {"status": "OK", "report_path": str(report_path)}

    def _stub_work_intake_check(args):
        ws = Path(str(args.workspace_root))
        intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
        _write_json(intake_path, {"version": "v1", "generated_at": _now_iso(), "items": []})
        return {"status": "OK", "work_intake_path": str(intake_path.relative_to(ws))}

    def _stub_exec_ticket(args):
        ws = Path(str(args.workspace_root))
        exec_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
        _write_json(
            exec_path,
            {
                "version": "v1",
                "generated_at": _now_iso(),
                "entries": [],
                "applied_count": 0,
                "planned_count": 0,
                "idle_count": 0,
                "selected_count": 0,
                "skipped_count": 0,
                "skipped_by_reason": {},
                "decision_needed_count": 0,
            },
        )
        return {
            "status": "OK",
            "work_intake_exec_path": str(exec_path.relative_to(ws)),
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
            "selected_count": 0,
            "skipped_count": 0,
            "skipped_by_reason": {},
            "decision_needed_count": 0,
        }

    def _stub_system_status(args):
        ws = Path(str(args.workspace_root))
        report_path = ws / ".cache" / "reports" / "system_status.v1.json"
        _write_json(report_path, {"version": "v1", "generated_at": _now_iso(), "status": "OK"})
        return {"status": "OK", "report_path": str(report_path.relative_to(ws))}

    def _stub_portfolio_status(args):
        ws = Path(str(args.workspace_root))
        report_path = ws / ".cache" / "reports" / "portfolio_status.v1.json"
        _write_json(report_path, {"version": "v1", "generated_at": _now_iso(), "status": "OK"})
        return {"status": "OK", "report_path": str(report_path.relative_to(ws))}

    airunner_tick_mod.cmd_ui_snapshot = _stub_ui_snapshot
    airunner_tick_mod.cmd_work_intake_check = _stub_work_intake_check
    airunner_tick_mod.cmd_work_intake_exec_ticket = _stub_exec_ticket
    airunner_tick_mod.cmd_system_status = _stub_system_status
    airunner_tick_mod.cmd_portfolio_status = _stub_portfolio_status

    run_airunner_tick = airunner_tick_mod.run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_poll_first_enforcement"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
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

    smoke_stub = (
        "import json,sys;"
        "json.dump({'rc':0}, open(sys.argv[1],'w'));"
    )
    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v2.json",
        {
            "version": "v2",
            "jobs": {
                "max_running": 1,
                "max_poll_per_tick": 1,
                "poll_interval_seconds": 0,
                "timeout_seconds": 60,
                "stale_after_seconds": 3600,
                "smoke_full": {
                    "enabled": True,
                    "timeout_seconds": 60,
                    "poll_interval_seconds": 0,
                    "max_concurrent": 1,
                    "cooldown_seconds": 0,
                },
                "stuck_job": {
                    "max_polls_without_progress": 0,
                    "stale_after_seconds": 3600,
                    "action_on_stale": "ARCHIVE",
                },
                "archive": {"keep_last_n": 50, "ttl_days": 7},
                "allowed_job_types": ["SMOKE_FULL"],
                "network_required_job_types": [],
                "smoke_full_cmd": [sys.executable, "-c", smoke_stub, "{rc_path}"],
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

    run_airunner_tick(workspace_root=ws)

    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        raise SystemExit("airrunner_poll_first_enforcement_contract_test failed: report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ops_called = report.get("ops_called")
    if ops_called != ["airunner-jobs-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airrunner_poll_first_enforcement_contract_test failed: expected poll-only ops")
    if int(report.get("queued_before") or 0) < 1:
        raise SystemExit("airrunner_poll_first_enforcement_contract_test failed: queued_before must be >= 1")

    print(json.dumps({"status": report.get("status", "OK")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
