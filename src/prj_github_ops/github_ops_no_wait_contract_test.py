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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import start_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_no_wait"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False)
    if res.get("status") not in {"IDLE", "SKIP", "WARN"}:
        raise SystemExit("github_ops_no_wait_contract_test failed: expected IDLE/SKIP/WARN when network disabled")

    idx_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    if not idx_path.exists():
        raise SystemExit("github_ops_no_wait_contract_test failed: jobs_index missing")
    idx = _load_json(idx_path)
    jobs = idx.get("jobs") if isinstance(idx, dict) else None
    if not isinstance(jobs, list) or not jobs:
        raise SystemExit("github_ops_no_wait_contract_test failed: jobs_index empty")

    if any(str(j.get("status") or "") in {"QUEUED", "RUNNING"} for j in jobs if isinstance(j, dict)):
        raise SystemExit("github_ops_no_wait_contract_test failed: network disabled must not leave running jobs")

    job_id = res.get("job_id")
    if job_id and not any(str(j.get("job_id") or "") == str(job_id) for j in jobs if isinstance(j, dict)):
        raise SystemExit("github_ops_no_wait_contract_test failed: job_id not found in jobs_index")

    ws_two = repo_root / ".cache" / "ws_github_ops_no_wait_2"
    if ws_two.exists():
        shutil.rmtree(ws_two)
    ws_two.mkdir(parents=True, exist_ok=True)
    res_two = start_github_ops_job(workspace_root=ws_two, kind="PR_OPEN", dry_run=False)
    if res.get("job_id") and res_two.get("job_id") and res.get("job_id") != res_two.get("job_id"):
        raise SystemExit("github_ops_no_wait_contract_test failed: job_id must be deterministic")

    print(json.dumps({"status": "OK", "job_id": res.get("job_id")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
