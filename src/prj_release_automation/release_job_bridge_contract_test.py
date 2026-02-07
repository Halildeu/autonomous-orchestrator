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

    from src.prj_release_automation.release_engine import run_release_check

    ws = repo_root / ".cache" / "ws_release_job_bridge"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res = run_release_check(workspace_root=ws, channel="rc", chat=False)
    manifest_rel = str(res.get("release_manifest_path") or "")
    if not manifest_rel:
        raise SystemExit("release_job_bridge_contract_test failed: release_manifest_path missing")
    manifest_path = ws / manifest_rel
    if not manifest_path.exists():
        raise SystemExit("release_job_bridge_contract_test failed: release_manifest not written")

    related_job_id = res.get("related_job_id")
    related_job_status = res.get("related_job_status")
    if not related_job_id:
        raise SystemExit("release_job_bridge_contract_test failed: related_job_id missing")
    if related_job_status not in {"IDLE", "SKIP", "RUNNING", "WARN", "OK", None}:
        raise SystemExit("release_job_bridge_contract_test failed: related_job_status unexpected")

    print(json.dumps({"status": "OK", "related_job_id": related_job_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
