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

    ws = repo_root / ".cache" / "ws_system_status_deploy_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    deploy_report = {
        "version": "v1",
        "generated_at": "2026-01-09T00:00:00Z",
        "workspace_root": str(ws),
        "status": "OK",
        "policy_source": "core",
        "policy_hash": "hash",
        "network_enabled": False,
        "mode": "dry_run_only",
        "allowed_kinds": ["DEPLOY_STATIC_FE"],
        "jobs_summary": {
            "total": 1,
            "by_status": {
                "QUEUED": 0,
                "RUNNING": 0,
                "PASS": 0,
                "FAIL": 0,
                "TIMEOUT": 0,
                "KILLED": 0,
                "SKIP": 1
            }
        },
        "jobs_index_path": ".cache/deploy/jobs_index.v1.json",
        "last_job": {
            "job_id": "job-1",
            "kind": "DEPLOY_STATIC_FE",
            "status": "SKIP",
            "job_report_path": ".cache/reports/deploy_jobs/deploy_job_job-1.v1.json",
            "skip_reason": "DRYRUN_OK",
            "error_code": "POLICY_BLOCKED",
            "updated_at": "2026-01-09T00:00:00Z"
        },
        "notes": []
    }
    _write_json(ws / ".cache" / "reports" / "deploy_report.v1.json", deploy_report)

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("system_status_deploy_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    deploy = sections.get("deploy") if isinstance(sections, dict) else None
    if not isinstance(deploy, dict):
        raise SystemExit("system_status_deploy_surface_contract_test failed: missing deploy section")
    if deploy.get("last_deploy_job_id") != "job-1":
        raise SystemExit("system_status_deploy_surface_contract_test failed: job id mismatch")
    if deploy.get("last_deploy_report_path") != ".cache/reports/deploy_report.v1.json":
        raise SystemExit("system_status_deploy_surface_contract_test failed: report path mismatch")

    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)
    if ui_payload.get("last_deploy_job_id") != "job-1":
        raise SystemExit("system_status_deploy_surface_contract_test failed: ui job id mismatch")
    if ui_payload.get("last_deploy_report_path") != ".cache/reports/deploy_report.v1.json":
        raise SystemExit("system_status_deploy_surface_contract_test failed: ui report path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
