from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_generated_at(obj: dict) -> dict:
    trimmed = dict(obj)
    trimmed.pop("generated_at", None)
    trimmed.pop("notes", None)
    return trimmed


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import build_github_ops_report, poll_github_ops_job, start_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    report = build_github_ops_report(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "github_ops_report.v1.json"
    if not report_path.exists():
        raise SystemExit("github_ops_contract_test failed: report missing")

    report_schema_path = repo_root / "schemas" / "github-ops-report.schema.v1.json"
    Draft202012Validator(_load_json(report_schema_path)).validate(_load_json(report_path))

    report2 = build_github_ops_report(workspace_root=ws)
    if _strip_generated_at(report) != _strip_generated_at(report2):
        raise SystemExit("github_ops_contract_test failed: report not deterministic")

    job_start = start_github_ops_job(workspace_root=ws, kind="pr_list", dry_run=True)
    if job_start.get("status") != "SKIP":
        raise SystemExit("github_ops_contract_test failed: job should be SKIP for dry_run")

    job_report_path = ws / ".cache" / "reports" / "github_ops_jobs" / f"github_ops_job_{job_start.get('job_id')}.v1.json"
    if not job_report_path.exists():
        raise SystemExit("github_ops_contract_test failed: job report missing")

    job_schema_path = repo_root / "schemas" / "github-ops-job.schema.v1.json"
    Draft202012Validator(_load_json(job_schema_path)).validate(_load_json(job_report_path))

    poll = poll_github_ops_job(workspace_root=ws, job_id=str(job_start.get("job_id") or ""))
    if poll.get("status") not in {"SKIP", "PASS", "RUNNING", "QUEUED"}:
        raise SystemExit("github_ops_contract_test failed: poll status invalid")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
