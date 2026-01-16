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

    from src.extensions.prj_deploy.deploy_jobs import deploy_job_poll, deploy_job_start

    ws = repo_root / ".cache" / "ws_deploy_jobs_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    start = deploy_job_start(workspace_root=ws, kind="DEPLOY_STATIC_FE", payload_ref="LOCAL_DRYRUN")
    if start.get("status") not in {"QUEUED", "SKIP"}:
        raise SystemExit("deploy_jobs_contract_test failed: start status")
    job_id = str(start.get("job_id") or "")
    if not job_id:
        raise SystemExit("deploy_jobs_contract_test failed: missing job_id")

    poll = deploy_job_poll(workspace_root=ws, job_id=job_id)
    if poll.get("status") != "SKIP":
        raise SystemExit("deploy_jobs_contract_test failed: poll status")
    job_report_path = poll.get("job_report_path") if isinstance(poll, dict) else None
    if not isinstance(job_report_path, str) or not job_report_path:
        raise SystemExit("deploy_jobs_contract_test failed: job_report_path")
    job_report = ws / job_report_path
    if not job_report.exists():
        raise SystemExit("deploy_jobs_contract_test failed: job_report missing")
    job_obj = _load_json(job_report)
    skip_reason = str(job_obj.get("skip_reason") or "")
    if skip_reason not in {"DRYRUN_OK", "NETWORK_DISABLED"}:
        raise SystemExit("deploy_jobs_contract_test failed: skip_reason")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
