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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import poll_github_ops_jobs

    ws = repo_root / ".cache" / "ws_github_ops_poll_max"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    job_old = "job-old"
    job_new = "job-new"
    rc_old = ws / ".cache" / "github_ops" / "jobs" / job_old / "rc.json"
    rc_new = ws / ".cache" / "github_ops" / "jobs" / job_new / "rc.json"
    _write_json(rc_old, {"rc": 0, "fingerprint": "old"})
    _write_json(rc_new, {"rc": 0, "fingerprint": "new"})

    jobs = [
        {
            "version": "v1",
            "job_id": job_old,
            "kind": "PR_OPEN",
            "status": "RUNNING",
            "created_at": "2026-01-11T00:00:00Z",
            "updated_at": "2026-01-11T00:00:00Z",
            "workspace_root": str(ws),
            "dry_run": False,
            "live_gate": False,
            "attempts": 1,
            "error_code": "",
            "skip_reason": "",
            "signature_hash": "sig-old",
            "evidence_paths": [".cache/reports/github_ops_jobs/github_ops_job_job-old.v1.json"],
            "notes": [],
        },
        {
            "version": "v1",
            "job_id": job_new,
            "kind": "PR_OPEN",
            "status": "RUNNING",
            "created_at": "2026-01-11T00:01:00Z",
            "updated_at": "2026-01-11T00:01:00Z",
            "workspace_root": str(ws),
            "dry_run": False,
            "live_gate": False,
            "attempts": 1,
            "error_code": "",
            "skip_reason": "",
            "signature_hash": "sig-new",
            "evidence_paths": [".cache/reports/github_ops_jobs/github_ops_job_job-new.v1.json"],
            "notes": [],
        },
    ]
    jobs_index = {
        "version": "v1",
        "generated_at": "2026-01-11T00:02:00Z",
        "workspace_root": str(ws),
        "status": "OK",
        "jobs": jobs,
        "counts": {
            "total": 2,
            "queued": 0,
            "running": 2,
            "pass": 0,
            "fail": 0,
            "timeout": 0,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json", jobs_index)

    res = poll_github_ops_jobs(workspace_root=ws, max_jobs=1)
    polled = res.get("polled_jobs") if isinstance(res.get("polled_jobs"), list) else []
    if len(polled) != 1:
        raise SystemExit("github_ops_job_poll_max_contract_test failed: polled_count != 1")
    if str(polled[0].get("job_id") or "") != job_old:
        raise SystemExit("github_ops_job_poll_max_contract_test failed: oldest job should be polled first")

    idx = _load_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json")
    updated_jobs = idx.get("jobs") if isinstance(idx.get("jobs"), list) else []
    status_map = {str(j.get("job_id") or ""): str(j.get("status") or "") for j in updated_jobs if isinstance(j, dict)}
    if status_map.get(job_old) != "PASS":
        raise SystemExit("github_ops_job_poll_max_contract_test failed: old job not updated")
    if status_map.get(job_new) not in {"RUNNING", "QUEUED"}:
        raise SystemExit("github_ops_job_poll_max_contract_test failed: new job should remain running/queued")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
