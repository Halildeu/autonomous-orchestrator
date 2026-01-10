from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def _write_preflight_stamp(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "preflight_stamp.v1.json",
        {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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


def _load_report(ws: Path) -> dict:
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_tick import run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_lock_budget_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json",
        {
            "version": "v1",
            "enabled": True,
            "max_runtime_seconds_per_day": 3600,
            "schedule": {
                "mode": "interval",
                "interval_seconds": 900,
                "jitter_seconds": 0,
                "active_hours": {"tz": "UTC", "start": "00:00", "end": "23:59"},
                "weekday_only": False,
            },
            "lock_ttl_seconds": 900,
            "heartbeat_interval_seconds": 300,
            "watchdog": {
                "enabled": True,
                "heartbeat_stale_seconds": 1200,
                "action": "CLEAR_STALE_LOCK_THEN_POLL_ONLY",
                "max_recoveries_per_day": 3,
            },
            "job_policy": {
                "max_running_jobs": 1,
                "poll_interval_seconds": 0,
                "closeout_ttl_days": 7,
                "keep_last_n": 50,
            },
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
    now = datetime.now(timezone.utc)

    # Fresh lock => IDLE LOCKED
    lock_path = ws / ".cache" / "airunner" / "airunner_lock.v1.json"
    fresh_expires = now + timedelta(minutes=10)
    _write_json(
        lock_path,
        {
            "version": "v1",
            "lock_id": "lock-fresh",
            "acquired_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": fresh_expires.isoformat().replace("+00:00", "Z"),
            "ttl_seconds": 600,
            "workspace_root": str(ws),
            "notes": ["contract_test"],
        },
    )

    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    if report.get("error_code") != "LOCKED":
        raise SystemExit("airunner_lock_budget_contract_test failed: expected LOCKED")

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass

    # Stale lock => poll-only
    stale_expires = now - timedelta(minutes=1)
    _write_json(
        lock_path,
        {
            "version": "v1",
            "lock_id": "lock-stale",
            "acquired_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": stale_expires.isoformat().replace("+00:00", "Z"),
            "ttl_seconds": 1,
            "workspace_root": str(ws),
            "notes": ["contract_test"],
        },
    )
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "status": "WARN",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "poll-only-queued",
                    "job_type": "SMOKE_FULL",
                    "kind": "SMOKE_FULL",
                    "workspace_root": str(ws),
                    "status": "QUEUED",
                    "created_at": now.isoformat().replace("+00:00", "Z"),
                    "started_at": now.isoformat().replace("+00:00", "Z"),
                    "last_poll_at": now.isoformat().replace("+00:00", "Z"),
                    "updated_at": now.isoformat().replace("+00:00", "Z"),
                    "attempts": 0,
                    "pid": None,
                    "rc": None,
                    "policy_hash": "test",
                    "evidence_paths": [],
                    "notes": ["queued"],
                    "polls_without_progress": 0,
                    "last_progress_at": now.isoformat().replace("+00:00", "Z"),
                }
            ],
            "counts": {"total": 1, "queued": 1, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    if report.get("ops_called") != ["airunner-jobs-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_lock_budget_contract_test failed: expected poll-only ops_called")

    # Runtime budget => WARN
    runtime_path = ws / ".cache" / "airunner" / "airunner_runtime.v1.json"
    _write_json(
        runtime_path,
        {
            "version": "v1",
            "date": now.date().isoformat(),
            "runtime_seconds": 5000,
            "last_tick_at": now.isoformat().replace("+00:00", "Z"),
            "notes": ["contract_test"],
        },
    )
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    if report.get("error_code") != "RUNTIME_BUDGET_EXCEEDED":
        raise SystemExit("airunner_lock_budget_contract_test failed: expected RUNTIME_BUDGET_EXCEEDED")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
