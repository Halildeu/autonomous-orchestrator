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

    from src.prj_github_ops.github_ops import poll_github_ops_job

    ws = repo_root / ".cache" / "ws_github_ops_pr_open_parse"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    job_id = "job-pr-open-parse"
    now = "2026-01-11T00:00:00Z"
    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": "PR_OPEN",
        "status": "RUNNING",
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(ws),
        "dry_run": False,
        "live_gate": True,
        "attempts": 1,
        "error_code": "",
        "skip_reason": "",
        "notes": [],
        "evidence_paths": [],
    }

    jobs_index = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(ws),
        "status": "OK",
        "jobs": [job],
        "counts": {
            "total": 1,
            "queued": 0,
            "running": 1,
            "pass": 0,
            "fail": 0,
            "timeout": 0,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json", jobs_index)

    fixture_path = repo_root / "fixtures" / "github_ops" / "pr_open_response.v1.json"
    fixture = _load_json(fixture_path)

    rc_path = ws / ".cache" / "github_ops" / "jobs" / job_id / "rc.json"
    rc_payload = {
        "rc": 0,
        "payload": fixture,
    }
    _write_json(rc_path, rc_payload)

    res = poll_github_ops_job(workspace_root=ws, job_id=job_id)
    report_path = res.get("job_report_path")
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: missing job report path")

    report = _load_json(ws / report_path)
    if report.get("pr_url") != fixture.get("html_url"):
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_url not captured")
    if report.get("pr_html_url") != fixture.get("html_url"):
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_html_url not captured")
    if report.get("pr_number") != fixture.get("number"):
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_number not captured")
    if report.get("pr_state") != fixture.get("state"):
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_state not captured")
    base_ref = ""
    if isinstance(fixture.get("base"), dict):
        base_ref = fixture.get("base", {}).get("ref", "")
    if report.get("pr_base") != base_ref:
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_base not captured")
    head_ref = ""
    if isinstance(fixture.get("head"), dict):
        head_ref = fixture.get("head", {}).get("ref", "")
    if report.get("pr_head") != head_ref:
        raise SystemExit("github_ops_pr_open_parse_contract_test failed: pr_head not captured")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
