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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_github_ops"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    t1 = "2026-01-08T00:00:00Z"
    t2 = "2026-01-08T00:10:00Z"
    signature = "sig-gh-ops-1"

    report = {
        "version": "v1",
        "generated_at": t2,
        "workspace_root": str(ws),
        "signals": [],
        "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
    }
    _write_json(ws / ".cache" / "reports" / "github_ops_report.v1.json", report)

    jobs_index = {
        "version": "v1",
        "generated_at": t2,
        "workspace_root": str(ws),
        "jobs": [
            {
                "version": "v1",
                "job_id": "job-1",
                "kind": "PR_OPEN",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": t1,
                "started_at": t1,
                "updated_at": t1,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "DEMO_PREREQ_FAIL",
                "signature_hash": signature,
            },
            {
                "version": "v1",
                "job_id": "job-2",
                "kind": "PR_OPEN",
                "workspace_root": str(ws),
                "status": "FAIL",
                "created_at": t2,
                "started_at": t2,
                "updated_at": t2,
                "attempts": 1,
                "evidence_paths": [],
                "notes": [],
                "failure_class": "DEMO_PREREQ_FAIL",
                "signature_hash": signature,
            },
        ],
        "notes": [],
    }
    _write_json(ws / ".cache" / "github_ops" / "jobs_index.v1.json", jobs_index)

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: work_intake missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: items missing")
    gh_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "GITHUB_OPS"]
    if len(gh_items) != 1:
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: expected 1 deduped GITHUB_OPS item")
    last_seen = str(gh_items[0].get("last_seen") or "")
    if last_seen != t2:
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: last_seen must be latest job")

    cooldowns_path = ws / ".cache" / "index" / "intake_cooldowns.v1.json"
    if not cooldowns_path.exists():
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: cooldowns missing")
    cooldowns = json.loads(cooldowns_path.read_text(encoding="utf-8"))
    notes = cooldowns.get("notes") if isinstance(cooldowns, dict) else None
    notes = [str(n) for n in notes if isinstance(n, str)] if isinstance(notes, list) else []
    if not any(n.startswith("github_ops_suppressed=") for n in notes):
        raise SystemExit("work_intake_github_ops_mapping_contract_test failed: suppressed note missing")

    print(json.dumps({"status": "OK", "github_ops_items": len(gh_items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
