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

    from src.prj_airunner.airunner_tick import run_airunner_tick

    ws = repo_root / ".cache" / "ws_airunner_tick_decision"
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
                    "github-ops-job-start",
                    "github-ops-job-poll",
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

    _write_preflight_stamp(ws)
    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_github_ops.override.v1.json",
        {
            "version": "v1",
            "network_enabled": False,
            "allowed_actions": ["PR_OPEN", "PR_POLL", "CI_POLL", "MERGE", "RELEASE_RC", "RELEASE_FINAL"],
        },
    )

    now = _now_iso()
    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "WARN",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "gh-job-1",
                    "kind": "PR_POLL",
                    "workspace_root": str(ws),
                    "status": "QUEUED",
                    "created_at": now,
                    "started_at": now,
                    "last_poll_at": now,
                    "updated_at": now,
                    "attempts": 0,
                    "evidence_paths": [],
                    "notes": [],
                }
            ],
            "notes": [],
        },
    )

    res_poll = run_airunner_tick(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "airunner_tick.v1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("ops_called") != ["github-ops-job-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_tick_decision_contract_test failed: poll-only tick must not start jobs")

    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": [],
            "notes": [],
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "github_ops_report.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "WARN",
            "signals": ["dirty_tree"],
            "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
            "notes": [],
        },
    )

    res_start = run_airunner_tick(workspace_root=ws)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("ops_called") != ["work-intake-check", "github-ops-job-start", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_tick_decision_contract_test failed: start-only tick must not poll jobs")

    print(
        json.dumps(
            {"status": "OK", "poll_status": res_poll.get("status"), "start_status": res_start.get("status")},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
