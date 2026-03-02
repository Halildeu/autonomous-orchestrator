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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import start_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_pr_open_live_gate"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    test_env_flag = "GITHUB_OPS_TEST_LIVE_FLAG"
    test_env_key = "GITHUB_OPS_TEST_LIVE_TOKEN"

    override = {
        "version": "v1",
        "network_enabled": True,
        "live_gate": {
            "enabled": True,
            "require_env_key_present": True,
            "env_flag": test_env_flag,
            "env_key": test_env_key,
        },
        "auth": {
            "mode": "bearer",
            "token_env": test_env_key,
        },
        "notes": ["contract_test_override=true"],
    }
    _write_json(ws / ".cache" / "policy_overrides" / "policy_github_ops.override.v1.json", override)

    old_flag = os.environ.get(test_env_flag)
    old_key = os.environ.get(test_env_key)
    os.environ[test_env_flag] = "1"
    os.environ.pop(test_env_key, None)

    try:
        res = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False)
        if res.get("status") not in {"IDLE", "SKIP", "WARN"}:
            raise SystemExit("github_ops_pr_open_live_gate_contract_test failed: status must be non-fatal")
        if res.get("error_code") not in {"AUTH_MISSING", "NETWORK_DISABLED", "LIVE_GATE_DISABLED"}:
            raise SystemExit("github_ops_pr_open_live_gate_contract_test failed: error_code must be gate-related")
        if not res.get("decision_needed", False):
            raise SystemExit("github_ops_pr_open_live_gate_contract_test failed: decision_needed expected")
    finally:
        if old_flag is None:
            os.environ.pop(test_env_flag, None)
        else:
            os.environ[test_env_flag] = old_flag
        if old_key is None:
            os.environ.pop(test_env_key, None)
        else:
            os.environ[test_env_key] = old_key

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
