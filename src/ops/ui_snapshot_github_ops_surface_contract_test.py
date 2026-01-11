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

    ws = repo_root / ".cache" / "ws_ui_snapshot_github_ops_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    job_id = "job-pr-open-2"
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
        "pr_url": "https://example.com/pr/456",
        "pr_number": 456,
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

    run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)

    idx = _load_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json")
    counts = idx.get("counts") if isinstance(idx, dict) else {}
    expected_total = int(counts.get("total") or 0) if isinstance(counts, dict) else 0
    expected_skip = int(counts.get("skip") or 0) if isinstance(counts, dict) else 0

    summary = ui_payload.get("github_ops_summary") if isinstance(ui_payload, dict) else None
    if not isinstance(summary, dict):
        raise SystemExit("ui_snapshot_github_ops_surface_contract_test failed: missing github_ops_summary")
    if summary.get("jobs_total") != expected_total:
        raise SystemExit("ui_snapshot_github_ops_surface_contract_test failed: jobs_total mismatch")
    by_status = summary.get("jobs_by_status") if isinstance(summary.get("jobs_by_status"), dict) else {}
    if by_status.get("skip") != expected_skip:
        raise SystemExit("ui_snapshot_github_ops_surface_contract_test failed: skip count mismatch")
    last_pr = summary.get("last_pr_open") if isinstance(summary.get("last_pr_open"), dict) else {}
    if last_pr.get("job_id") != job_id:
        raise SystemExit("ui_snapshot_github_ops_surface_contract_test failed: job id mismatch")
    if last_pr.get("pr_url") != "https://example.com/pr/456":
        raise SystemExit("ui_snapshot_github_ops_surface_contract_test failed: pr_url mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
