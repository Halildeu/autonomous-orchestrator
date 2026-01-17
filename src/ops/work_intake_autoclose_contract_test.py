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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build, _intake_id

    ws = repo_root / ".cache" / "ws_work_intake_autoclose_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    req_path = ws / ".cache" / "index" / "manual_requests" / "REQ-TEST.v1.json"
    _write_json(
        req_path,
        {
            "version": "v1",
            "request_id": "REQ-TEST",
            "kind": "note",
            "impact_scope": "doc-only",
            "artifact_type": "request",
            "domain": "general",
            "requires_core_change": False,
            "text": "contract",
            "attachments": [],
        },
    )

    intake_id = _intake_id("MANUAL_REQUEST", "REQ-TEST", "TICKET")
    exec_report_path = ws / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    _write_json(
        exec_report_path,
        {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "entries": [
                {
                    "intake_id": intake_id,
                    "status": "APPLIED",
                }
            ],
        },
    )

    jobs_index_path = ws / ".cache" / "airunner" / "jobs_index.v1.json"
    _write_json(
        jobs_index_path,
        {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "job-pass-1",
                    "job_type": "SMOKE_FULL",
                    "kind": "SMOKE_FULL",
                    "workspace_root": str(ws),
                    "status": "PASS",
                    "failure_class": "PASS",
                    "signature_hash": "sig-pass",
                    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "evidence_paths": [],
                    "notes": [],
                }
            ],
            "counts": {
                "total": 1,
                "queued": 0,
                "running": 0,
                "pass": 1,
                "fail": 0,
                "timeout": 0,
                "killed": 0,
                "skip": 0
            },
            "notes": []
        },
    )

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_autoclose_contract_test failed: build status")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    data = json.loads(intake_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else []

    applied_closed = [i for i in items if i.get("intake_id") == intake_id and i.get("status") == "DONE"]
    if not applied_closed:
        raise SystemExit("work_intake_autoclose_contract_test failed: EXEC_APPLIED not closed")

    pass_items = [i for i in items if i.get("source_type") == "JOB_STATUS" and i.get("status") == "DONE"]
    if not pass_items:
        raise SystemExit("work_intake_autoclose_contract_test failed: JOB_STATUS PASS not closed")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
