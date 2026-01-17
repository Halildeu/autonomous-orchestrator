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
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_system_status_github_ops_failure_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = "2026-01-11T00:00:00Z"
    job = {
        "version": "v1",
        "job_id": "job-fail",
        "kind": "PR_OPEN",
        "status": "FAIL",
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(ws),
        "dry_run": False,
        "live_gate": True,
        "attempts": 1,
        "error_code": "HTTP_ERROR",
        "failure_class": "AUTH",
        "notes": [],
        "evidence_paths": [],
    }
    jobs_index = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(ws),
        "status": "WARN",
        "jobs": [job],
        "counts": {
            "total": 1,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 1,
            "timeout": 0,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json", jobs_index)

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    github_ops = sections.get("github_ops") if isinstance(sections, dict) else None
    if not isinstance(github_ops, dict):
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: missing github_ops section")
    failure_summary = github_ops.get("failure_summary") if isinstance(github_ops, dict) else None
    if not isinstance(failure_summary, dict):
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: missing failure_summary")
    if int(failure_summary.get("total_fail") or 0) != 1:
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: total_fail mismatch")
    by_class = failure_summary.get("by_class") if isinstance(failure_summary.get("by_class"), dict) else {}
    if int(by_class.get("AUTH") or 0) != 1:
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: AUTH count mismatch")

    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)
    summary = ui_payload.get("github_ops_summary") if isinstance(ui_payload, dict) else None
    if not isinstance(summary, dict):
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: missing ui github_ops_summary")
    ui_failure = summary.get("failure_summary") if isinstance(summary, dict) else None
    if not isinstance(ui_failure, dict):
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: missing ui failure_summary")
    if int(ui_failure.get("total_fail") or 0) != 1:
        raise SystemExit("system_status_github_ops_failure_surface_contract_test failed: ui total_fail mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
