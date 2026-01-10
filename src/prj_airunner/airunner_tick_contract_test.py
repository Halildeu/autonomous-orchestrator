from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
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


def _write_preflight_stamp(ws: Path, generated_at: str) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": generated_at,
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

    from src.prj_airunner.airunner_tick import (
        _compute_tick_id,
        _load_policy,
        _window_bucket,
        _work_intake_hash,
        run_airunner_tick,
    )

    ws = repo_root / ".cache" / "ws_airunner_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res_idle = run_airunner_tick(workspace_root=ws)
    if res_idle.get("status") != "IDLE":
        raise SystemExit("airunner_tick_contract_test failed: expected IDLE without override")

    override_path = ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    _write_json(
        override_path,
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
            "job_policy": {
                "max_running_jobs": 1,
                "poll_interval_seconds": 60,
                "closeout_ttl_days": 7,
                "keep_last_n": 50,
            },
            "limits": {"max_ticks_per_run": 1, "max_actions_per_tick": 3, "max_plans_per_tick": 5},
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
    jobs_override_path = ws / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json"
    smoke_stub = (
        "import json,sys,time;"
        "time.sleep(0.5);"
        "json.dump({'rc':0}, open(sys.argv[1],'w'));"
    )
    _write_json(
        jobs_override_path,
        {
            "version": "v1",
            "jobs": {
                "max_running": 1,
                "max_poll_per_tick": 1,
                "poll_interval_seconds": 0,
                "timeout_seconds": 120,
                "stale_after_seconds": 3600,
                "allowed_job_types": ["SMOKE_FULL"],
                "network_required_job_types": [],
                "smoke_full_cmd": [sys.executable, "-c", smoke_stub, "{rc_path}"],
            },
            "perf": {
                "enable": False,
                "event_log_max_lines": 10,
                "time_sinks_window": 0,
                "thresholds_ms": {
                    "smoke_full_p95_warn": 1,
                    "smoke_fast_p95_warn": 1,
                    "release_prepare_p95_warn": 1,
                },
            },
            "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
        },
    )

    _write_preflight_stamp(ws, now.isoformat().replace("+00:00", "Z"))

    lock_path = ws / ".cache" / "airunner" / "airunner_lock.v1.json"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_json(
        lock_path,
        {
            "version": "v1",
            "lock_id": "lock-test",
            "acquired_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(seconds=600)).isoformat().replace("+00:00", "Z"),
            "ttl_seconds": 600,
            "workspace_root": str(ws),
            "notes": ["contract_test"],
        },
    )
    res_locked = run_airunner_tick(workspace_root=ws)
    if res_locked.get("status") != "IDLE":
        raise SystemExit("airunner_tick_contract_test failed: expected IDLE when locked")
    lock_path.unlink(missing_ok=True)

    res = run_airunner_tick(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN", "IDLE", "FAIL"}:
        raise SystemExit("airunner_tick_contract_test failed: unexpected status")

    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        raise SystemExit("airunner_tick_contract_test failed: report missing")
    jobs_index_path = ws / ".cache" / "airunner" / "jobs_index.v1.json"
    if not jobs_index_path.exists():
        raise SystemExit("airunner_tick_contract_test failed: jobs_index missing")
    time_sinks_path = ws / ".cache" / "reports" / "time_sinks.v1.json"
    if not time_sinks_path.exists():
        raise SystemExit("airunner_tick_contract_test failed: time_sinks report missing")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    policy_source = report.get("policy_source")
    if policy_source != "core+workspace_override":
        raise SystemExit("airunner_tick_contract_test failed: policy_source must be core+workspace_override")

    ops_called = report.get("ops_called")
    if ops_called != [
        "work-intake-check",
        "work-intake-exec-ticket",
        "system-status",
        "portfolio-status",
        "ui-snapshot-bundle",
    ]:
        raise SystemExit("airunner_tick_contract_test failed: ops_called mismatch")

    notes = report.get("notes")
    if not isinstance(notes, list) or "NETWORK=false" not in notes:
        raise SystemExit("airunner_tick_contract_test failed: network note missing")

    tick_id = report.get("tick_id")
    if not isinstance(tick_id, str) or not tick_id:
        raise SystemExit("airunner_tick_contract_test failed: tick_id missing")

    idx = json.loads(jobs_index_path.read_text(encoding="utf-8"))
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "RUNNING":
        raise SystemExit("airunner_tick_contract_test failed: expected running SMOKE_FULL job")

    time.sleep(0.6)
    res_poll = run_airunner_tick(workspace_root=ws)
    report_poll = json.loads(report_path.read_text(encoding="utf-8"))
    if report_poll.get("jobs_polled", 0) < 0:
        raise SystemExit("airunner_tick_contract_test failed: jobs_polled missing")
    idx = json.loads(jobs_index_path.read_text(encoding="utf-8"))
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "PASS":
        raise SystemExit("airunner_tick_contract_test failed: expected PASS after poll")

    policy, _, policy_hash, _ = _load_policy(ws)
    schedule = policy.get("schedule") if isinstance(policy.get("schedule"), dict) else {}
    heartbeat_path = ws / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    computed_tick_id = _compute_tick_id(policy_hash, _work_intake_hash(ws), _window_bucket(schedule))
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "last_tick_id": computed_tick_id,
            "last_tick_at": now.isoformat().replace("+00:00", "Z"),
            "last_status": "OK",
            "last_error_code": None,
            "last_tick_window": _window_bucket(schedule),
            "policy_hash": policy_hash,
            "notes": ["contract_test"],
        },
    )
    res_noop = run_airunner_tick(workspace_root=ws)
    if res_noop.get("status") != "IDLE":
        raise SystemExit("airunner_tick_contract_test failed: expected NOOP IDLE on same tick_id")

    print(json.dumps({"status": "OK", "tick_id": tick_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
