from __future__ import annotations

import json
import os
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
    from src.ops.decision_inbox import run_decision_inbox_build

    ws = repo_root / ".cache" / "ws_github_ops_decision_seed"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("KERNEL_API_GITHUB_LIVE", None)

    res = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False)
    if res.get("decision_needed") is not True:
        raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: decision_needed must be true")

    res_second = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False)
    if res_second.get("decision_needed") is not True:
        if res_second.get("error_code") not in {"COOLDOWN_ACTIVE", "RATE_LIMIT", "JOB_ALREADY_RUNNING"}:
            raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: decision_needed missing on repeat")

    seeds_dir = ws / ".cache" / "index" / "decision_seeds"
    seeds = sorted(seeds_dir.glob("SEED-*.v1.json")) if seeds_dir.exists() else []
    if len(seeds) != 1:
        raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: seed dedup expected 1 file")

    inbox = run_decision_inbox_build(workspace_root=ws)
    if inbox.get("decisions_count", 0) <= 0:
        raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: inbox missing decision")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: decision inbox missing")
    obj = _load_json(inbox_path)
    items = obj.get("items") if isinstance(obj.get("items"), list) else []
    kinds = {str(i.get("decision_kind") or "") for i in items if isinstance(i, dict)}
    if "NETWORK_LIVE_ENABLE" not in kinds:
        raise SystemExit("decision_seed_live_pr_prereq_contract_test failed: NETWORK_LIVE_ENABLE missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
