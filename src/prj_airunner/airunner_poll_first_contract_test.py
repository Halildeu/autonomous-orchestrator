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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def _write_preflight_stamp(ws: Path, *, soft_exceeded: int = 0) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "gates": {
                "validate_schemas": "PASS",
                "smoke_fast": "PASS",
                "script_budget": {
                    "hard_exceeded": 0,
                    "soft_exceeded": int(soft_exceeded),
                    "status": "OK",
                },
            },
            "overall": "PASS",
            "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_tick import run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_poll_first"
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
            "job_policy": {"max_running_jobs": 1, "poll_interval_seconds": 0, "closeout_ttl_days": 7, "keep_last_n": 50},
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

    _write_preflight_stamp(ws)

    smoke_stub = (
        "import json,sys,time;"
        "time.sleep(0.2);"
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
                    "cooldown_seconds": 0
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

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "WARN",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "poll-first-queued",
                    "job_type": "SMOKE_FULL",
                    "kind": "SMOKE_FULL",
                    "workspace_root": str(ws),
                    "status": "QUEUED",
                    "created_at": now,
                    "started_at": now,
                    "last_poll_at": now,
                    "updated_at": now,
                    "attempts": 0,
                    "pid": None,
                    "rc": None,
                    "policy_hash": "test",
                    "evidence_paths": [],
                    "notes": ["queued"],
                    "polls_without_progress": 0,
                    "last_progress_at": now,
                }
            ],
            "counts": {"total": 1, "queued": 1, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    res = run_airunner_tick(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        raise SystemExit("airunner_poll_first_contract_test failed: report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))

    if int(report.get("jobs_polled") or 0) < 1:
        raise SystemExit("airunner_poll_first_contract_test failed: jobs_polled must be >= 1")
    ops_called = report.get("ops_called")
    if ops_called != ["airunner-jobs-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_poll_first_contract_test failed: ops_called must be poll-only")

    _write_json(
        ws / ".cache" / "index" / "work_intake.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "items": [],
        },
    )
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": [],
            "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    res_2 = run_airunner_tick(workspace_root=ws)
    report_path_2 = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    report_2 = json.loads(report_path_2.read_text(encoding="utf-8"))
    if int(report_2.get("jobs_started") or 0) < 1:
        raise SystemExit("airrunner_poll_first_contract_test failed: jobs_started must be >= 1 on second tick")

    if res_2.get("status") not in {"OK", "WARN"}:
        raise SystemExit("airrunner_poll_first_contract_test failed: second tick must not be FAIL")

    print(json.dumps({"status": res.get("status", "OK")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
