from __future__ import annotations

import json
import shutil
import sys
import time
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

    ws = repo_root / ".cache" / "ws_airunner_jobs_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    smoke_stub = (
        "import json,sys,time;"
        "time.sleep(0.5);"
        "json.dump({'rc':0}, open(sys.argv[1],'w'));"
    )
    policy_override = {
        "version": "v1",
        "jobs": {
            "max_running": 1,
            "max_poll_per_tick": 1,
            "poll_interval_seconds": 0,
            "timeout_seconds": 10,
            "stale_after_seconds": 3600,
            "allowed_job_types": ["SMOKE_FULL"],
            "network_required_job_types": [],
            "smoke_full_cmd": [sys.executable, "-c", smoke_stub, "{rc_path}"],
        },
        "perf": {"enable": False, "event_log_max_lines": 10, "time_sinks_window": 0, "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1}},
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }

    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="contract",
        policy_hash="test",
        policy=policy_override,
    )

    jobs_path = ws / ".cache" / "airunner" / "jobs_index.v1.json"
    if not jobs_path.exists():
        raise SystemExit("airunner_jobs_contract_test failed: jobs_index missing")
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    if not isinstance(jobs, list) or not jobs:
        raise SystemExit("airunner_jobs_contract_test failed: jobs list missing")
    job = jobs[0]
    if job.get("status") != "RUNNING" or not isinstance(job.get("pid"), int):
        raise SystemExit("airunner_jobs_contract_test failed: SMOKE_FULL must start running with pid")

    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="contract",
        policy_hash="test",
        policy=policy_override,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "RUNNING":
        raise SystemExit("airunner_jobs_contract_test failed: running job should remain RUNNING before rc")

    time.sleep(0.6)
    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="contract",
        policy_hash="test",
        policy=policy_override,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "PASS":
        raise SystemExit("airunner_jobs_contract_test failed: expected PASS after rc")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    many_jobs = []
    for i in range(60):
        started_at = now - timedelta(minutes=i)
        many_jobs.append(
            {
                "version": "v1",
                "job_id": f"prune-{i:03d}",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "PASS",
                "created_at": started_at.isoformat().replace("+00:00", "Z"),
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "last_poll_at": started_at.isoformat().replace("+00:00", "Z"),
                "updated_at": started_at.isoformat().replace("+00:00", "Z"),
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
            }
        )
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": many_jobs,
            "counts": {
                "total": 60,
                "queued": 0,
                "running": 0,
                "pass": 60,
                "fail": 0,
                "timeout": 0,
                "killed": 0,
                "skip": 0,
            },
            "notes": [],
        },
    )

    policy_prune = {
        "version": "v1",
        "jobs": {
            "max_running": 1,
            "max_poll_per_tick": 1,
            "poll_interval_seconds": 0,
            "keep_last_n": 50,
            "ttl_seconds": 0,
            "timeout_seconds": 10,
            "stale_after_seconds": 3600,
            "allowed_job_types": [],
            "network_required_job_types": [],
        },
        "perf": {"enable": False, "event_log_max_lines": 1, "time_sinks_window": 0, "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1}},
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }
    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="prune",
        policy_hash="test",
        policy=policy_prune,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    if not isinstance(jobs, list) or len(jobs) != 50:
        raise SystemExit("airunner_jobs_contract_test failed: expected 50 jobs after prune")
    archive_path = ws / ".cache" / "reports" / "jobs_archive.v1.json"
    if not archive_path.exists():
        raise SystemExit("airunner_jobs_contract_test failed: archive missing")

    print(json.dumps({"status": "OK", "job_status": job.get("status")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
