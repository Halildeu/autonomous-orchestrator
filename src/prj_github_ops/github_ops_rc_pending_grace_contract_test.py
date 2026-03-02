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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_job(index_payload: dict, job_id: str) -> dict:
    jobs = index_payload.get("jobs") if isinstance(index_payload.get("jobs"), list) else []
    for job in jobs:
        if isinstance(job, dict) and str(job.get("job_id") or "") == job_id:
            return job
    raise SystemExit("github_ops_rc_pending_grace_contract_test failed: job not found")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import poll_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_rc_pending_grace"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    job_id = "job-rc-pending-grace"
    now = _now_iso()
    jobs_index = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(ws),
        "status": "OK",
        "jobs": [
            {
                "version": "v1",
                "job_id": job_id,
                "kind": "PR_OPEN",
                "status": "RUNNING",
                "created_at": now,
                "updated_at": now,
                "started_at": now,
                "workspace_root": str(ws),
                "dry_run": False,
                "live_gate": True,
                "attempts": 1,
                "pid": 999999,
                "error_code": "",
                "skip_reason": "",
                "notes": [],
                "evidence_paths": [],
            }
        ],
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
    }
    jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    _write_json(jobs_index_path, jobs_index)

    first = poll_github_ops_job(workspace_root=ws, job_id=job_id)
    if str(first.get("status") or "") != "RUNNING":
        raise SystemExit("github_ops_rc_pending_grace_contract_test failed: first poll must stay RUNNING")

    first_index = _load_json(jobs_index_path)
    first_job = _find_job(first_index, job_id)
    if str(first_job.get("error_code") or "") != "RC_PENDING":
        raise SystemExit("github_ops_rc_pending_grace_contract_test failed: expected RC_PENDING after first poll")

    notes = first_job.get("notes") if isinstance(first_job.get("notes"), list) else []
    stale_marker = "rc_pending_since:2025-01-01T00:00:00Z"
    notes = [x for x in notes if isinstance(x, str) and not x.startswith("rc_pending_since:")]
    notes.append(stale_marker)
    first_job["notes"] = notes
    first_job["error_code"] = "RC_PENDING"
    first_job["status"] = "RUNNING"
    _write_json(jobs_index_path, first_index)

    second = poll_github_ops_job(workspace_root=ws, job_id=job_id)
    if str(second.get("status") or "") != "FAIL":
        raise SystemExit("github_ops_rc_pending_grace_contract_test failed: second poll must fail after grace")

    second_index = _load_json(jobs_index_path)
    second_job = _find_job(second_index, job_id)
    if str(second_job.get("error_code") or "") != "RC_MISSING":
        raise SystemExit("github_ops_rc_pending_grace_contract_test failed: expected RC_MISSING after grace")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
