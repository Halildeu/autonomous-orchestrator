from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"github_ops_refactor_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import poll_github_ops_jobs, run_github_ops_check

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir(parents=True, exist_ok=True)
        os.environ["KERNEL_API_LLM_LIVE"] = "0"

        check = run_github_ops_check(workspace_root=ws, chat=False)
        _must(isinstance(check, dict), "run_github_ops_check payload must be dict")
        _must(str(check.get("status") or "") in {"OK", "WARN", "FAIL", "IDLE"}, "invalid check status")
        _must(bool(check.get("jobs_index_path")), "jobs_index_path missing")

        poll = poll_github_ops_jobs(workspace_root=ws, max_jobs=1)
        _must(isinstance(poll, dict), "poll_github_ops_jobs payload must be dict")
        _must(str(poll.get("status") or "") in {"OK", "IDLE"}, "poll status must be OK/IDLE")

    print(
        json.dumps(
            {
                "status": "OK",
                "check_status": check.get("status"),
                "poll_status": poll.get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
