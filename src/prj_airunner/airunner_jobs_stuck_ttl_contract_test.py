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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_jobs import update_jobs
    from src.prj_airunner.airunner_jobs_lifecycle import cleanup_stuck_jobs

    ws = repo_root / ".cache" / "ws_airunner_jobs_stuck_ttl"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    policy = {
        "version": "v2",
        "jobs": {
            "max_running": 1,
            "max_poll_per_tick": 1,
            "poll_interval_seconds": 0,
            "keep_last_n": 50,
            "ttl_seconds": 86400,
            "timeout_seconds": 60,
            "stale_after_seconds": 3600,
            "stuck_job": {
                "max_polls_without_progress": 2,
                "stale_after_seconds": 1800,
                "action_on_stale": "ARCHIVE",
            },
            "archive": {"keep_last_n": 50, "ttl_days": 7},
            "classify": {"release_publish_no_network": "SKIP"},
            "allowed_job_types": ["RELEASE_PUBLISH"],
            "network_required_job_types": ["RELEASE_PUBLISH"],
            "smoke_full": {
                "enabled": False,
                "timeout_seconds": 1,
                "poll_interval_seconds": 1,
                "max_concurrent": 1,
                "cooldown_seconds": 0,
            },
        },
        "perf": {
            "enable": False,
            "event_log_max_lines": 1,
            "time_sinks_window": 0,
            "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1},
        },
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }

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
                    "job_id": "release-publish-queued",
                    "job_type": "RELEASE_PUBLISH",
                    "kind": "RELEASE_PUBLISH",
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
                }
            ],
            "counts": {"total": 1, "queued": 1, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    index, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="tick-1",
        policy_hash="test",
        policy=policy,
        lifecycle_policy={"max_running_jobs": 1, "poll_interval_seconds": 0, "closeout_ttl_days": 7, "keep_last_n": 50},
        allow_enqueue=False,
        poll_only=True,
    )
    jobs = index.get("jobs") if isinstance(index, dict) else []
    if not jobs or str(jobs[0].get("status") or "") != "SKIP":
        raise SystemExit("airunner_jobs_stuck_ttl_contract_test failed: queued job must be SKIP when network disabled")

    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=4000)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stuck_job = {
        "version": "v1",
        "job_id": "stuck-job",
        "job_type": "SMOKE_FULL",
        "kind": "SMOKE_FULL",
        "workspace_root": str(ws),
        "status": "RUNNING",
        "created_at": stale_time,
        "started_at": stale_time,
        "last_poll_at": stale_time,
        "updated_at": stale_time,
        "polls_without_progress": 2,
        "last_progress_at": stale_time,
        "attempts": 1,
        "pid": None,
        "rc": None,
        "policy_hash": "test",
        "evidence_paths": [],
        "notes": ["stuck"],
    }
    jobs, stats, _ = cleanup_stuck_jobs(
        workspace_root=ws,
        jobs=[stuck_job],
        action_on_stale="ARCHIVE",
        max_polls_without_progress=2,
        stale_after_seconds=1800,
    )
    if not jobs or str(jobs[0].get("status") or "") != "SKIP":
        raise SystemExit("airunner_jobs_stuck_ttl_contract_test failed: stuck job must be SKIP")
    if not jobs[0].get("archived"):
        raise SystemExit("airunner_jobs_stuck_ttl_contract_test failed: stuck job must be archived")
    if int(stats.get("archived", 0)) < 1:
        raise SystemExit("airrunner_jobs_stuck_ttl_contract_test failed: archived count missing")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
