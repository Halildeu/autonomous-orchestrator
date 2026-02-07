from __future__ import annotations

import json
import re
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


def _assert_workspace_scoped(path: Path, workspace_root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(workspace_root.resolve())
    except Exception:
        raise SystemExit(f"airunner_auto_run_job_contract_test failed: {label} not workspace-scoped")


def _assert_no_secrets(text: str) -> None:
    patterns = [
        r"ghp_[A-Za-z0-9]{10,}",
        r"github_pat_[A-Za-z0-9_]{10,}",
        r"(?i)token\\s*=",
        r"(?i)authorization\\s*:",
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            raise SystemExit("airunner_auto_run_job_contract_test failed: secret-like pattern detected")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_auto_run_job import poll_auto_run, start_auto_run

    ws = repo_root / ".cache" / "ws_airunner_auto_run_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    payload = start_auto_run(
        workspace_root=ws,
        stop_at_local="07:00",
        timezone_name="UTC",
        mode="autopilot",
        job_kind="SMOKE_FULL",
        dry_run=True,
    )
    if payload.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("airunner_auto_run_job_contract_test failed: start status")

    job_id = str(payload.get("job_id") or "")
    if not job_id:
        raise SystemExit("airunner_auto_run_job_contract_test failed: job_id missing")

    job_path = ws / str(payload.get("job_path") or "")
    if not job_path.exists():
        raise SystemExit("airrunner_auto_run_job_contract_test failed: job state missing")
    _assert_workspace_scoped(job_path, ws, "job_state")

    job_obj = _load_json(job_path)
    if job_obj.get("status") != "SKIP":
        raise SystemExit("airrunner_auto_run_job_contract_test failed: dry_run should SKIP")

    poll_payload = poll_auto_run(workspace_root=ws, job_id=job_id, max_polls=1)
    if poll_payload.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("airrunner_auto_run_job_contract_test failed: poll status")
    poll_reports = poll_payload.get("poll_reports") if isinstance(poll_payload.get("poll_reports"), list) else []
    if not poll_reports:
        raise SystemExit("airrunner_auto_run_job_contract_test failed: poll report missing")

    job_obj = _load_json(job_path)
    if int(job_obj.get("poll_count") or 0) < 1:
        raise SystemExit("airrunner_auto_run_job_contract_test failed: poll_count not incremented")

    poll_path = ws / str(poll_reports[-1])
    if not poll_path.exists():
        raise SystemExit("airrunner_auto_run_job_contract_test failed: poll report missing")
    _assert_workspace_scoped(poll_path, ws, "poll_report")

    index_path = ws / str(poll_payload.get("jobs_index_path") or "")
    if not index_path.exists():
        raise SystemExit("airrunner_auto_run_job_contract_test failed: index missing")
    _assert_workspace_scoped(index_path, ws, "index")

    _assert_no_secrets(job_path.read_text(encoding="utf-8"))
    _assert_no_secrets(poll_path.read_text(encoding="utf-8"))

    print(json.dumps({"status": "OK", "job_id": job_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
