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

    from src.prj_github_ops.github_ops import poll_github_ops_job, start_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_lifecycle"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    start = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False)
    if start.get("status") not in {"IDLE", "SKIP", "WARN"}:
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: expected non-fatal status when network disabled")
    index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    if not index_path.exists():
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: jobs_index missing")
    index = _load_json(index_path)
    jobs = index.get("jobs") if isinstance(index, dict) else None
    if not isinstance(jobs, list) or not jobs:
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: jobs_index empty")
    if any(str(j.get("status") or "") in {"RUNNING", "QUEUED"} for j in jobs if isinstance(j, dict)):
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: network disabled must not leave running jobs")
    job_id = str(start.get("job_id") or "")
    if not job_id:
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: job_id missing")

    poll = poll_github_ops_job(workspace_root=ws, job_id=job_id)
    if poll.get("status") not in {"SKIP", "PASS", "FAIL"}:
        raise SystemExit("github_ops_job_lifecycle_contract_test failed: poll status invalid")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
