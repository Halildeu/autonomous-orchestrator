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


def _dedup_key(job_id: str, job_type: str, failure_class: str, signature_hash: str = "") -> str:
    bucket = "INCIDENT" if failure_class == "CORE_BREAK" else "TICKET"
    sig = signature_hash or job_id
    return f"{job_type}|{bucket}|{sig}"


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
                "job_id": "job-demo-2b",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-2b.stderr.log"],
                "notes": [],
                "failure_class": "POLICY_TIME_LIMIT",
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
            {
                "version": "v1",
                "job_id": "job-demo-6",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "SKIP",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-6.stderr.log"],
                "notes": [],
                "skip_reason": "AUTH_MISSING",
            },
            {
                "version": "v1",
                "job_id": "job-demo-7",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "SKIP",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [".cache/reports/jobs/smoke_full_job-demo-7.stderr.log"],
                "notes": [],
                "skip_reason": "POLICY_BLOCKED",
            },
        ],
        "counts": {
            "total": 8,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 5,
            "timeout": 1,
            "killed": 0,
            "skip": 2,
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
    if buckets.get(_dedup_key("job-demo-1", "SMOKE_FULL", "DEMO_PREREQ_FAIL")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: DEMO_PREREQ_FAIL must be TICKET")
    if buckets.get(_dedup_key("job-demo-2", "SMOKE_FULL", "OTHER")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: OTHER fail must be TICKET")
    if buckets.get(_dedup_key("job-demo-2b", "SMOKE_FULL", "POLICY_TIME_LIMIT")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: POLICY_TIME_LIMIT must be TICKET")
    if buckets.get(_dedup_key("job-demo-3", "SMOKE_FULL", "")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: TIMEOUT must be TICKET")
    if buckets.get(_dedup_key("job-demo-4", "SMOKE_FULL", "DEMO_CATALOG_PARSE")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: DEMO_CATALOG_PARSE must be TICKET")
    if buckets.get(_dedup_key("job-demo-5", "SMOKE_FULL", "CORE_BREAK")) != "INCIDENT":
        raise SystemExit("work_intake_jobstatus_contract_test failed: CORE_BREAK must be INCIDENT")
    if buckets.get(_dedup_key("job-demo-6", "SMOKE_FULL", "")) != "TICKET":
        raise SystemExit("work_intake_jobstatus_contract_test failed: AUTH_MISSING must be TICKET")
    if buckets.get(_dedup_key("job-demo-7", "SMOKE_FULL", "")) != "ROADMAP":
        raise SystemExit("work_intake_jobstatus_contract_test failed: POLICY_BLOCKED must be ROADMAP")

    print(json.dumps({"status": "OK", "items": len(items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
