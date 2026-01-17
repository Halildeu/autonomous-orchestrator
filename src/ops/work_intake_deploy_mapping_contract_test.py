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
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_deploy_mapping"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    start = deploy_job_start(workspace_root=ws, kind="DEPLOY_STATIC_FE", payload_ref="LOCAL_DRYRUN")
    job_id = str(start.get("job_id") or "")
    if not job_id:
        raise SystemExit("work_intake_deploy_mapping_contract_test failed: job_id")

    poll = deploy_job_poll(workspace_root=ws, job_id=job_id)
    if poll.get("status") != "SKIP":
        raise SystemExit("work_intake_deploy_mapping_contract_test failed: poll status")

    intake = run_work_intake_build(workspace_root=ws)
    intake_path = intake.get("work_intake_path") if isinstance(intake, dict) else None
    if not isinstance(intake_path, str) or not intake_path:
        raise SystemExit("work_intake_deploy_mapping_contract_test failed: missing intake path")

    intake_obj = _load_json(ws / intake_path)
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    deploy_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "DEPLOY_JOB"]
    if not deploy_items:
        raise SystemExit("work_intake_deploy_mapping_contract_test failed: missing deploy items")

    matched = False
    for item in deploy_items:
        suggested = item.get("suggested_extension") if isinstance(item.get("suggested_extension"), list) else []
        if "PRJ-DEPLOY" not in {str(x) for x in suggested if isinstance(x, str)}:
            continue
        if item.get("bucket") != "ROADMAP":
            raise SystemExit("work_intake_deploy_mapping_contract_test failed: bucket not ROADMAP")
        matched = True
        break

    if not matched:
        raise SystemExit("work_intake_deploy_mapping_contract_test failed: suggested_extension missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
