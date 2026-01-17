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

    import src.prj_github_ops.github_ops as gh

    ws = repo_root / ".cache" / "ws_smoke_fast_local_job_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    override_path = ws / ".cache" / "policy_overrides" / "policy_github_ops.override.v1.json"
    _write_json(
        override_path,
        {
            "version": "v1",
            "network_enabled": False,
            "live_gate": {
                "enabled": False,
                "require_env_key_present": True,
                "env_flag": "KERNEL_API_GITHUB_LIVE",
                "env_key": "GITHUB_TOKEN",
            },
            "allowed_actions": ["SMOKE_FAST"],
            "notes": ["CONTRACT_TEST"],
        },
    )

    original_spawn = gh._spawn_job_process
    gh._spawn_job_process = lambda *args, **kwargs: (12345, [".cache/github_ops/jobs/demo/rc.json"])
    try:
        res = gh.start_github_ops_job(workspace_root=ws, kind="SMOKE_FAST", dry_run=False)
    finally:
        gh._spawn_job_process = original_spawn

    if res.get("status") != "RUNNING":
        raise SystemExit("smoke_fast_local_job_contract_test failed: expected RUNNING job")
    if not res.get("job_id"):
        raise SystemExit("smoke_fast_local_job_contract_test failed: missing job_id")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
