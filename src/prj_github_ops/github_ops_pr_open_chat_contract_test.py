from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _parse_last_json(lines: list[str]) -> dict:
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            return json.loads(raw)
        except Exception:
            continue
    return {}


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_github_ops_pr_open_chat"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env.pop("KERNEL_API_GITHUB_LIVE", None)

    cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "github-ops-pr-open",
        "--workspace-root",
        str(ws),
        "--dry-run",
        "false",
        "--chat",
        "true",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(repo_root))
    if proc.returncode != 0:
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: command non-zero")
    out_lines = proc.stdout.strip().splitlines()

    if not any(line.strip() == "PREVIEW:" for line in out_lines):
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: missing PREVIEW")
    if not any(line.strip() == "RESULT:" for line in out_lines):
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: missing RESULT")

    payload = _parse_last_json(out_lines)
    if not payload:
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: missing JSON payload")
    if payload.get("decision_needed") is not True:
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: decision_needed must be true offline")
    gate = payload.get("gate_state") if isinstance(payload.get("gate_state"), dict) else {}
    if not isinstance(gate.get("network_enabled"), bool):
        raise SystemExit("github_ops_pr_open_chat_contract_test failed: gate_state missing")

    seed_path = payload.get("decision_seed_path")
    if isinstance(seed_path, str) and seed_path:
        if not (ws / seed_path).exists():
            raise SystemExit("github_ops_pr_open_chat_contract_test failed: decision seed missing")
    inbox_path = payload.get("decision_inbox_path")
    if payload.get("decision_needed") is True:
        if not isinstance(inbox_path, str) or not inbox_path:
            raise SystemExit("github_ops_pr_open_chat_contract_test failed: decision_inbox_path missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
