from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"github_ops_scope_prune_contract_test failed: {message}")


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import build_github_ops_report

    ws = repo_root / ".cache" / "ws_github_ops_scope_prune_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    jobs_index = {
        "version": "v1",
        "generated_at": _iso(now),
        "workspace_root": str(ws),
        "status": "WARN",
        "notes": [],
        "jobs": [
            {
                "version": "v1",
                "job_id": "external-fail",
                "kind": "SMOKE_FULL",
                "status": "FAIL",
                "created_at": _iso(now - timedelta(hours=1)),
                "updated_at": _iso(now - timedelta(hours=1)),
                "workspace_root": str(repo_root / ".cache" / "ws_external"),
            },
            {
                "version": "v1",
                "job_id": "local-timeout-stale",
                "kind": "SMOKE_FULL",
                "status": "TIMEOUT",
                "created_at": _iso(now - timedelta(days=20)),
                "updated_at": _iso(now - timedelta(days=20)),
                "workspace_root": str(ws),
            },
            {
                "version": "v1",
                "job_id": "local-pass",
                "kind": "SMOKE_FULL",
                "status": "PASS",
                "created_at": _iso(now - timedelta(hours=2)),
                "updated_at": _iso(now - timedelta(hours=2)),
                "workspace_root": str(ws),
            },
        ],
        "counts": {"total": 3, "queued": 0, "running": 0, "pass": 1, "fail": 1, "timeout": 1, "killed": 0, "skip": 0},
    }
    jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    jobs_index_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_index_path.write_text(json.dumps(jobs_index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    report = build_github_ops_report(workspace_root=ws)
    summary = report.get("jobs_summary") if isinstance(report.get("jobs_summary"), dict) else {}
    by_status = summary.get("by_status") if isinstance(summary.get("by_status"), dict) else {}
    _must(int(summary.get("total", -1)) == 1, "workspace scope total should be 1")
    _must(int(by_status.get("PASS", -1)) == 1, "workspace scoped PASS should be 1")
    _must(int(by_status.get("FAIL", -1)) == 0, "external FAIL must be excluded from summary")
    _must(int(by_status.get("TIMEOUT", -1)) == 0, "stale TIMEOUT must be pruned/excluded")

    failure_summary = report.get("failure_summary") if isinstance(report.get("failure_summary"), dict) else {}
    _must(int(failure_summary.get("total_fail", -1)) == 0, "failure_summary should ignore external FAIL")

    notes = report.get("notes") if isinstance(report.get("notes"), list) else []
    _must(any(str(n).startswith("jobs_stale_pruned=") for n in notes), "stale prune note missing")
    _must(any(str(n).startswith("jobs_workspace_filtered=") for n in notes), "workspace filter note missing")

    report_jobs = report.get("jobs") if isinstance(report.get("jobs"), list) else []
    report_job_ids = sorted(str(item.get("job_id") or "") for item in report_jobs if isinstance(item, dict))
    _must(report_job_ids == ["local-pass"], "report should only surface in-scope jobs")

    saved_index = json.loads(jobs_index_path.read_text(encoding="utf-8"))
    saved_jobs = saved_index.get("jobs") if isinstance(saved_index.get("jobs"), list) else []
    saved_ids = sorted(str(item.get("job_id") or "") for item in saved_jobs if isinstance(item, dict))
    _must("local-timeout-stale" not in saved_ids, "stale timeout should be removed from jobs index")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
