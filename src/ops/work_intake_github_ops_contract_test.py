from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_github_ops_intake_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    script_budget_path = ws / ".cache" / "script_budget" / "report.json"
    script_budget_path.parent.mkdir(parents=True, exist_ok=True)
    script_budget_path.write_text(
        _dump_json(
            {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": "OK",
                "exceeded_soft": [],
                "exceeded_hard": [],
            }
        ),
        encoding="utf-8",
    )

    job_id = "job-001"
    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": "pr_list",
        "status": "FAIL",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "workspace_root": str(ws),
        "dry_run": True,
        "live_gate": False,
        "attempts": 0,
        "error_code": "FAILED",
        "failure_class": "OTHER",
        "signature_hash": _hash_text("OTHER|demo"),
        "evidence_paths": [".cache/reports/github_ops_jobs/github_ops_job_job-001.v1.json"],
        "result_paths": [],
        "notes": [],
    }

    jobs_index = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws),
        "status": "OK",
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
    jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    jobs_index_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_index_path.write_text(_dump_json(jobs_index), encoding="utf-8")

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws),
        "status": "WARN",
        "live_gate": {
            "enabled": False,
            "env_flag": "KERNEL_API_GITHUB_LIVE",
            "env_key_present": False,
            "allowed_ops": ["pr_list"],
        },
        "git_state": {
            "dirty_tree": True,
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "index_lock": False,
        },
        "signals": ["dirty_tree"],
        "jobs_summary": {
            "total": 1,
            "by_status": {
                "QUEUED": 0,
                "RUNNING": 0,
                "PASS": 0,
                "FAIL": 1,
                "TIMEOUT": 0,
                "KILLED": 0,
                "SKIP": 0,
            },
        },
        "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
        "notes": [],
    }
    report_path = ws / ".cache" / "reports" / "github_ops_report.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report), encoding="utf-8")

    res1 = run_work_intake_build(workspace_root=ws)
    _ = res1
    work_intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    work_intake = json.loads(work_intake_path.read_text(encoding="utf-8"))
    items = [i for i in work_intake.get("items", []) if isinstance(i, dict) and i.get("source_type") == "GITHUB_OPS"]
    source_refs = {str(i.get("source_ref") or "") for i in items}
    buckets = {str(i.get("bucket") or "") for i in items}
    expected_job_ref = f"github_ops_sig:pr_list|FAIL|OTHER|{job['signature_hash']}"
    if len(items) != 2:
        raise SystemExit("work_intake_github_ops_contract_test failed: expected 2 github_ops items on first build")
    if buckets != {"TICKET"}:
        raise SystemExit("work_intake_github_ops_contract_test failed: bucket mapping invalid")
    if source_refs != {expected_job_ref, "github_ops:dirty_tree"}:
        raise SystemExit("work_intake_github_ops_contract_test failed: source refs mismatch")

    res2 = run_work_intake_build(workspace_root=ws)
    _ = res2
    work_intake2 = json.loads(work_intake_path.read_text(encoding="utf-8"))
    items2 = [i for i in work_intake2.get("items", []) if isinstance(i, dict) and i.get("source_type") == "GITHUB_OPS"]
    buckets2 = {str(i.get("bucket") or "") for i in items2}
    if len(items2) != 2 or buckets2 != {"TICKET"}:
        raise SystemExit("work_intake_github_ops_contract_test failed: cooldown output changed unexpectedly")
    cooldowns_path = ws / ".cache" / "index" / "intake_cooldowns.v1.json"
    cooldowns = json.loads(cooldowns_path.read_text(encoding="utf-8"))
    entries = cooldowns.get("entries") if isinstance(cooldowns, dict) else None
    if not isinstance(entries, dict):
        raise SystemExit("work_intake_github_ops_contract_test failed: cooldown entries missing")
    cooldown_key = f"github_ops|pr_list|OTHER|{job['signature_hash']}"
    entry = entries.get(cooldown_key) if isinstance(entries.get(cooldown_key), dict) else {}
    if int(entry.get("suppressed_count", 0)) != 1:
        raise SystemExit("work_intake_github_ops_contract_test failed: cooldown suppression counter mismatch")
    notes = cooldowns.get("notes") if isinstance(cooldowns, dict) else None
    notes = [str(n) for n in notes if isinstance(n, str)] if isinstance(notes, list) else []
    if "github_ops_suppressed=1" not in notes:
        raise SystemExit("work_intake_github_ops_contract_test failed: cooldown suppression note missing")

    print(json.dumps({"status": "OK", "github_ops_items": len(items2)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
