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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import start_github_ops_job

    ws_live = repo_root / ".cache" / "ws_github_ops_job_pipeline_live"
    if ws_live.exists():
        shutil.rmtree(ws_live)
    ws_live.mkdir(parents=True, exist_ok=True)

    start_live = start_github_ops_job(workspace_root=ws_live, kind="PR_OPEN", dry_run=False)
    if start_live.get("status") != "IDLE":
        raise SystemExit("github_ops_job_pipeline_contract_test failed: live gate must return IDLE when disabled")
    if start_live.get("error_code") not in {"NETWORK_DISABLED", "LIVE_GATE_DISABLED"}:
        raise SystemExit("github_ops_job_pipeline_contract_test failed: error_code must report network gate")

    ws_one = repo_root / ".cache" / "ws_github_ops_job_pipeline_one"
    if ws_one.exists():
        shutil.rmtree(ws_one)
    ws_one.mkdir(parents=True, exist_ok=True)
    start_one = start_github_ops_job(workspace_root=ws_one, kind="PR_OPEN", dry_run=True)
    ws_two = repo_root / ".cache" / "ws_github_ops_job_pipeline_2"
    if ws_two.exists():
        shutil.rmtree(ws_two)
    ws_two.mkdir(parents=True, exist_ok=True)
    start_two = start_github_ops_job(workspace_root=ws_two, kind="PR_OPEN", dry_run=True)
    if not start_one.get("job_id") or start_one.get("job_id") != start_two.get("job_id"):
        raise SystemExit("github_ops_job_pipeline_contract_test failed: job_id must be deterministic")

    print(json.dumps({"status": "OK", "workspace": str(ws_one)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
