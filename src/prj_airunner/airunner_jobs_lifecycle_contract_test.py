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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_jobs_lifecycle import closeout_jobs

    ws = repo_root / ".cache" / "ws_airunner_lifecycle_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    evidence_rel = ".cache/reports/jobs/smoke_full_demo.stderr.log"
    evidence_path = ws / evidence_rel
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("demo", encoding="utf-8")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    job = {
        "version": "v1",
        "job_id": "job-lifecycle-1",
        "job_type": "SMOKE_FULL",
        "kind": "SMOKE_FULL",
        "workspace_root": str(ws),
        "status": "PASS",
        "created_at": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "started_at": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "last_poll_at": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "updated_at": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "attempts": 1,
        "evidence_paths": [evidence_rel],
        "notes": [],
    }

    kept, stats, archive_paths = closeout_jobs(
        workspace_root=ws,
        jobs=[job],
        closeout_ttl_days=0,
        keep_last_n=1,
    )

    if stats.get("archived", 0) < 1:
        raise SystemExit("airunner_jobs_lifecycle_contract_test failed: archive count")
    if not archive_paths:
        raise SystemExit("airunner_jobs_lifecycle_contract_test failed: archive paths missing")
    archived_path = ws / archive_paths[0]
    if not archived_path.exists():
        raise SystemExit("airunner_jobs_lifecycle_contract_test failed: archived file missing")
    if evidence_path.exists():
        raise SystemExit("airunner_jobs_lifecycle_contract_test failed: original evidence not moved")

    kept_job = kept[0] if kept else {}
    if kept_job.get("archived") is not True:
        raise SystemExit("airunner_jobs_lifecycle_contract_test failed: archived flag missing")

    print(json.dumps({"status": "OK", "archived": stats.get("archived", 0)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
