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

    from src.prj_github_ops.github_ops import _run_pr_merge_job

    ws = repo_root / ".cache" / "ws_github_ops_merge_offline_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    # Ensure repo inference does not depend on local git remotes during the test.
    os.environ["GITHUB_REPOSITORY"] = "example/example"

    rc_path = ws / ".cache" / "reports" / "merge_offline.rc.json"
    fingerprint = "merge-offline-contract-test"

    # Intentionally choose a token env var that does not exist to guarantee no network calls.
    _run_pr_merge_job(
        str(rc_path),
        "",
        "CODEX_TEST_NO_TOKEN",
        "bearer",
        fingerprint,
        str(ws),
    )

    if not rc_path.exists():
        raise SystemExit("github_ops_merge_offline_contract_test failed: rc file missing")

    rc = _load_json(rc_path)
    if int(rc.get("rc") or 0) != 1:
        raise SystemExit("github_ops_merge_offline_contract_test failed: expected rc=1 (fail-closed)")
    if str(rc.get("error_code") or "") != "AUTH_MISSING":
        raise SystemExit("github_ops_merge_offline_contract_test failed: expected error_code=AUTH_MISSING")
    if str(rc.get("fingerprint") or "") != fingerprint:
        raise SystemExit("github_ops_merge_offline_contract_test failed: fingerprint mismatch")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

