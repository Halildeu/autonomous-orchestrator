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


def _load_report(ws: Path) -> dict:
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


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
    run_airunner_tick = airunner_tick_mod.run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_poll_first_conditional"
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
                    "github-ops-job-start",
                    "github-ops-job-poll",
                ],
                "require_strict_isolation": True,
            },
            "notes": ["PROGRAM_LED=true", "WORKSPACE_ONLY=true"],
        },
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
                "stuck_job": {"max_polls_without_progress": 0, "stale_after_seconds": 3600, "action_on_stale": "ARCHIVE"},
                "archive": {"keep_last_n": 50, "ttl_days": 7},
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
                    "job_id": "queued-1",
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

    run_airunner_tick(workspace_root=ws)
    report = _load_report(ws)
    ops_called = report.get("ops_called")
    if ops_called != ["airunner-jobs-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airrunner_poll_first_conditional_contract_test failed: expected poll-only when jobs active")
    if "github-ops-job-start" in (ops_called or []):
        raise SystemExit("airrunner_poll_first_conditional_contract_test failed: start should not run when jobs active")

    lock_path = ws / ".cache" / "airunner" / "airrunner_lock.v1.json"
    if lock_path.exists():
        lock_path.unlink()

    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "jobs": [],
            "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "jobs": [],
            "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "github_ops_report.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "OK",
            "signals": ["manual_check"],
            "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
        },
    )

    run_airunner_tick(workspace_root=ws)
    report2 = _load_report(ws)
    ops_called2 = report2.get("ops_called") or []
    if "github-ops-job-start" not in ops_called2:
        raise SystemExit("airrunner_poll_first_conditional_contract_test failed: expected start-only when idle")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
