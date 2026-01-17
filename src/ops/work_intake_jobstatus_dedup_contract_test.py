from __future__ import annotations

import json
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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_jobstatus_dedup"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    t1 = "2026-01-07T00:00:00Z"
    t2 = "2026-01-07T00:10:00Z"
    signature = "sig-demo-1"

    jobs_index = {
        "version": "v1",
        "generated_at": t2,
        "workspace_root": str(ws),
        "status": "WARN",
        "jobs": [
            {
                "version": "v1",
                "job_id": "job-1",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": t1,
                "started_at": t1,
                "last_poll_at": t1,
                "updated_at": t1,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "OTHER",
                "signature_hash": signature,
            },
            {
                "version": "v1",
                "job_id": "job-2",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": t2,
                "started_at": t2,
                "last_poll_at": t2,
                "updated_at": t2,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "DEMO_CATALOG_PARSE",
                "signature_hash": signature,
            },
        ],
        "counts": {
            "total": 2,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 2,
            "timeout": 0,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "airunner" / "jobs_index.v1.json", jobs_index)

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: items missing")
    job_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "JOB_STATUS"]
    if len(job_items) != 1:
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: expected 1 deduped job item")
    last_seen = str(job_items[0].get("last_seen") or "")
    if last_seen != t2:
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: last_seen must reflect latest job")

    jobs_index["jobs"].append(
        {
            "version": "v1",
            "job_id": "job-3",
            "job_type": "SMOKE_FULL",
            "kind": "SMOKE_FULL",
            "workspace_root": str(ws),
            "status": "FAIL",
            "created_at": t2,
            "started_at": t2,
            "last_poll_at": t2,
            "updated_at": t2,
            "attempts": 1,
            "evidence_paths": [],
            "notes": [],
            "failure_class": "CORE_BREAK",
            "signature_hash": signature,
        }
    )
    jobs_index["counts"]["total"] = 3
    jobs_index["counts"]["fail"] = 3
    _write_json(ws / ".cache" / "airunner" / "jobs_index.v1.json", jobs_index)

    run_work_intake_build(workspace_root=ws)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: items missing after escalation")
    job_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "JOB_STATUS"]
    if len(job_items) != 2:
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: escalation must create new item")
    buckets = {i.get("bucket") for i in job_items if isinstance(i, dict)}
    if "INCIDENT" not in buckets:
        raise SystemExit("work_intake_jobstatus_dedup_contract_test failed: CORE_BREAK must be INCIDENT")

    print(json.dumps({"status": "OK", "job_items": len(job_items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
