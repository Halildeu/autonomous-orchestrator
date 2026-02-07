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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_cooldown"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    signature = "sig-demo-1"
    jobs_index = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(ws),
        "status": "WARN",
        "jobs": [
            {
                "version": "v1",
                "job_id": "job-1",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "OTHER",
                "signature_hash": signature,
            },
            {
                "version": "v1",
                "job_id": "job-2",
                "job_type": "SMOKE_FULL",
                "kind": "SMOKE_FULL",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": now,
                "started_at": now,
                "last_poll_at": now,
                "updated_at": now,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "OTHER",
                "signature_hash": signature,
            },
        ],
        "counts": {
            "total": 2,
            "queued": 0,
            "running": 0,
            "pass": 0,
            "fail": 2,
            "timeout": 0,
            "killed": 0,
            "skip": 0,
        },
        "notes": [],
    }
    _write_json(ws / ".cache" / "airunner" / "jobs_index.v1.json", jobs_index)

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_cooldown_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_cooldown_contract_test failed: items missing")
    job_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "JOB_STATUS"]
    if len(job_items) != 1:
        raise SystemExit("work_intake_cooldown_contract_test failed: expected 1 job item after cooldown")

    cooldown_path = ws / ".cache" / "index" / "intake_cooldowns.v1.json"
    if not cooldown_path.exists():
        raise SystemExit("work_intake_cooldown_contract_test failed: cooldown index missing")
    cooldowns = json.loads(cooldown_path.read_text(encoding="utf-8"))
    entries = cooldowns.get("entries") if isinstance(cooldowns, dict) else None
    if not isinstance(entries, dict):
        raise SystemExit("work_intake_cooldown_contract_test failed: entries missing")
    key = f"SMOKE_FULL|TICKET|{signature}"
    entry = entries.get(key) if isinstance(entries.get(key), dict) else {}
    if int(entry.get("suppressed_count", 0)) != 1:
        raise SystemExit("work_intake_cooldown_contract_test failed: suppressed_count must be 1")

    print(json.dumps({"status": "OK", "job_items": len(job_items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
