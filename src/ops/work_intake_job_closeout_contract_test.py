from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_job_closeout"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "job-pass-1",
                    "kind": "PR_OPEN",
                    "status": "PASS",
                    "created_at": now,
                    "updated_at": now,
                    "workspace_root": str(ws),
                    "dry_run": True,
                    "live_gate": False,
                    "evidence_paths": [],
                    "notes": ["pass"],
                    "signature_hash": "sig-pass-1",
                }
            ],
            "counts": {"total": 1, "queued": 0, "running": 0, "pass": 1, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    _write_json(
        ws / ".cache" / "reports" / "github_ops_report.v1.json",
        {
            "version": "v1",
            "generated_at": now,
            "workspace_root": str(ws),
            "status": "OK",
            "signals": [],
            "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
        },
    )

    run_work_intake_build(workspace_root=ws)
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("work_intake_job_closeout_contract_test failed: work_intake missing")
    intake = _load_json(intake_path)
    items = intake.get("items") if isinstance(intake, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_job_closeout_contract_test failed: items missing")
    gh_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "GITHUB_OPS"]
    if len(gh_items) != 1:
        raise SystemExit("work_intake_job_closeout_contract_test failed: expected single GITHUB_OPS item")
    item = gh_items[0]
    if item.get("status") != "DONE":
        raise SystemExit("work_intake_job_closeout_contract_test failed: expected DONE status")
    if item.get("closed_reason") != "GITHUB_OPS_JOB_PASS":
        raise SystemExit("work_intake_job_closeout_contract_test failed: closed_reason mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
