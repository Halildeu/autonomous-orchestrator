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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_jobstatus"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    jobs_index = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(ws),
        "status": "WARN",
        "jobs": [
            {
                "version": "v1",
                "job_id": "job-demo-1",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-1.stderr.log"],
                "notes": [],
                "failure_class": "DEMO_PREREQ_FAIL",
            },
            {
                "version": "v1",
                "job_id": "job-demo-2",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-2.stderr.log"],
                "notes": [],
                "failure_class": "OTHER",
            },
            {
                "version": "v1",
                "job_id": "job-demo-3",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "TIMEOUT",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-3.stderr.log"],
                "notes": [],
            },
            {
                "version": "v1",
                "job_id": "job-demo-4",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-4.stderr.log"],
                "notes": [],
                "failure_class": "DEMO_CATALOG_PARSE",
            },
            {
                "version": "v1",
                "job_id": "job-demo-5",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-5.stderr.log"],
                "notes": [],
                "failure_class": "CORE_BREAK",
            },
        ],
        "counts": {
            "total": 5,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 4,
            "timeout": 1,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "airunner" / "jobs_index.v1.json", jobs_index)

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_jobstatus_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_jobstatus_contract_test failed: items missing")

    buckets = {item.get("source_ref"): item.get("bucket") for item in items if isinstance(item, dict)}
    if buckets.get("job-demo-1") != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: DEMO_PREREQ_FAIL must be TICKET")
    if buckets.get("job-demo-2") != "INCIDENT":
        raise SystemExit("work_intake_jobstatus_contract_test failed: OTHER fail must be INCIDENT")
    if buckets.get("job-demo-3") != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: TIMEOUT must be TICKET")
    if buckets.get("job-demo-4") != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: DEMO_CATALOG_PARSE must be TICKET")
    if buckets.get("job-demo-5") != "INCIDENT":
        raise SystemExit("work_intake_jobstatus_contract_test failed: CORE_BREAK must be INCIDENT")

    print(json.dumps({"status": "OK", "items": len(items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
