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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status

    ws = repo_root / ".cache" / "ws_system_status_github_ops_pr_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    job_id = "job-pr-open-1"
    job_report_rel = Path(".cache") / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json"
    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": "PR_OPEN",
        "status": "SKIP",
        "created_at": "2026-01-11T00:00:00Z",
        "updated_at": "2026-01-11T00:00:00Z",
        "workspace_root": str(ws),
        "dry_run": False,
        "live_gate": False,
        "attempts": 0,
        "error_code": "NO_NETWORK",
        "skip_reason": "NO_NETWORK",
        "pr_url": "https://example.com/pr/123",
        "pr_number": 123,
        "signature_hash": "sig",
        "evidence_paths": [str(job_report_rel)],
        "notes": [],
    }
    _write_json(ws / job_report_rel, job)

    jobs_index = {
        "version": "v1",
        "generated_at": "2026-01-11T00:00:00Z",
        "workspace_root": str(ws),
        "status": "OK",
        "jobs": [job],
        "counts": {
            "total": 1,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 0,
            "timeout": 0,
            "killed": 0,
            "skip": 1,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json", jobs_index)

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("system_status_github_ops_pr_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    github_ops = sections.get("github_ops") if isinstance(sections, dict) else None
    if not isinstance(github_ops, dict):
        raise SystemExit("system_status_github_ops_pr_surface_contract_test failed: missing github_ops section")
    last_pr = github_ops.get("last_pr_open") if isinstance(github_ops.get("last_pr_open"), dict) else None
    if not isinstance(last_pr, dict):
        raise SystemExit("system_status_github_ops_pr_surface_contract_test failed: missing last_pr_open")
    if last_pr.get("job_id") != job_id:
        raise SystemExit("system_status_github_ops_pr_surface_contract_test failed: job id mismatch")
    if last_pr.get("pr_url") != "https://example.com/pr/123":
        raise SystemExit("system_status_github_ops_pr_surface_contract_test failed: pr_url mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
