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

    ws_root = repo_root / ".cache" / "ws_github_ops_failure_parse"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    ws_root.mkdir(parents=True, exist_ok=True)

    cases = [
        (401, "AUTH"),
        (403, "PERMISSION"),
        (404, "NOT_FOUND"),
        (409, "CONFLICT"),
        (422, "VALIDATION"),
        (429, "RATE_LIMIT"),
        (500, "NETWORK"),
    ]
    now = "2026-01-11T00:00:00Z"
    token_like = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"

    for http_status, expected_class in cases:
        ws = ws_root / f"case_{http_status}"
        ws.mkdir(parents=True, exist_ok=True)
        job_id = f"job-{http_status}"
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

        rc_payload = {
            "rc": 1,
            "error_code": "HTTP_ERROR",
            "http_status": http_status,
            "endpoint": "https://api.github.com/repos/example/acme/pulls",
            "message": f"token {token_like}",
        }
        _write_json(ws / ".cache" / "github_ops" / "jobs" / job_id / "rc.json", rc_payload)

        res = poll_github_ops_job(workspace_root=ws, job_id=job_id)
        report_path = res.get("job_report_path")
        if not isinstance(report_path, str) or not report_path:
            raise SystemExit("github_ops_failure_parse_contract_test failed: missing job report path")

        report = _load_json(ws / report_path)
        if report.get("failure_class") != expected_class:
            raise SystemExit(
                f"github_ops_failure_parse_contract_test failed: {http_status} expected {expected_class}"
            )
        if report.get("http_status") != http_status:
            raise SystemExit("github_ops_failure_parse_contract_test failed: http_status missing")
        redacted = report.get("message_redacted") or ""
        if token_like in redacted:
            raise SystemExit("github_ops_failure_parse_contract_test failed: redaction missing")
        if "REDACTED" not in redacted:
            raise SystemExit("github_ops_failure_parse_contract_test failed: redaction marker missing")
        if not report.get("message_hash"):
            raise SystemExit("github_ops_failure_parse_contract_test failed: message_hash missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
