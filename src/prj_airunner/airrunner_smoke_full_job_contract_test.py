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

    ws = repo_root / ".cache" / "ws_airunner_smoke_full_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    smoke_stub = (
        "import json,sys,time;"
        "time.sleep(0.2);"
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
        "perf": {
            "enable": False,
            "event_log_max_lines": 1,
            "time_sinks_window": 0,
            "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1},
        },
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }

    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="t1",
        policy_hash="test",
        policy=policy_override,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "RUNNING":
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: expected RUNNING job")
    if not isinstance(job.get("pid"), int):
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: pid missing")
    rc_path = ws / ".cache" / "reports" / "jobs" / f"smoke_full_{job.get('job_id')}.rc.json"
    if not rc_path.parent.exists():
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: report directory missing")

    time.sleep(0.4)
    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="t1",
        policy_hash="test",
        policy=policy_override,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "PASS":
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: expected PASS after rc")
    if job.get("failure_class") != "PASS":
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: failure_class PASS required")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    timeout_job = {
        "version": "v1",
        "job_id": "smoke-timeout",
        "job_type": "SMOKE_FULL",
        "kind": "SMOKE_FULL",
        "workspace_root": str(ws),
        "status": "RUNNING",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "started_at": (now - timedelta(seconds=120)).isoformat().replace("+00:00", "Z"),
        "last_poll_at": (now - timedelta(seconds=120)).isoformat().replace("+00:00", "Z"),
        "updated_at": (now - timedelta(seconds=120)).isoformat().replace("+00:00", "Z"),
        "attempts": 1,
        "evidence_paths": [],
        "notes": [],
        "pid": None,
        "rc": None,
    }
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "status": "WARN",
            "jobs": [timeout_job],
            "counts": {
                "total": 1,
                "queued": 0,
                "running": 1,
                "pass": 0,
                "fail": 0,
                "timeout": 0,
                "killed": 0,
                "skip": 0,
            },
            "notes": [],
        },
    )

    policy_timeout = {
        "version": "v1",
        "jobs": {
            "max_running": 1,
            "max_poll_per_tick": 1,
            "poll_interval_seconds": 0,
            "timeout_seconds": 1,
            "stale_after_seconds": 3600,
            "allowed_job_types": [],
            "network_required_job_types": [],
        },
        "perf": {
            "enable": False,
            "event_log_max_lines": 1,
            "time_sinks_window": 0,
            "thresholds_ms": {"smoke_full_p95_warn": 1, "smoke_fast_p95_warn": 1, "release_prepare_p95_warn": 1},
        },
        "intake_mapping": {"time_sink_bucket": "TICKET", "time_sink_escalate_to_incident_after": 3},
    }

    idx, _, _ = update_jobs(
        workspace_root=ws,
        tick_id="t2",
        policy_hash="test",
        policy=policy_timeout,
    )
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    job = jobs[0] if isinstance(jobs, list) and jobs else {}
    if job.get("status") != "TIMEOUT":
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: expected TIMEOUT")
    if job.get("failure_class") != "TIMEOUT":
        raise SystemExit("airrunner_smoke_full_job_contract_test failed: failure_class TIMEOUT required")

    print(json.dumps({"status": "OK", "job_status": job.get("status")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
