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
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_historical_prune import run_work_intake_historical_prune

    ws = repo_root / ".cache" / "ws_work_intake_historical_prune_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    t1 = "2026-03-02T09:00:00Z"
    t2 = "2026-03-02T10:00:00Z"
    t3 = "2026-03-02T11:00:00Z"

    jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
    _write_json(
        jobs_index_path,
        {
            "version": "v1",
            "generated_at": t3,
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "job-merge-skip-old",
                    "kind": "MERGE",
                    "status": "SKIP",
                    "skip_reason": "DRY_RUN",
                    "failure_class": "",
                    "signature_hash": "sig-merge-old",
                    "created_at": t1,
                    "started_at": t1,
                    "last_poll_at": t1,
                    "updated_at": t1,
                },
                {
                    "version": "v1",
                    "job_id": "job-merge-pass-new",
                    "kind": "MERGE",
                    "status": "PASS",
                    "skip_reason": "",
                    "failure_class": "PASS",
                    "signature_hash": "sig-merge-new",
                    "created_at": t2,
                    "started_at": t2,
                    "last_poll_at": t2,
                    "updated_at": t2,
                },
                {
                    "version": "v1",
                    "job_id": "job-pr-open-fail",
                    "kind": "PR_OPEN",
                    "status": "FAIL",
                    "skip_reason": "",
                    "failure_class": "OTHER",
                    "signature_hash": "sig-pr-open",
                    "created_at": t3,
                    "started_at": t3,
                    "last_poll_at": t3,
                    "updated_at": t3,
                },
            ],
            "counts": {"total": 3, "queued": 0, "running": 0, "pass": 1, "fail": 1, "timeout": 0, "killed": 0, "skip": 1},
            "notes": [],
        },
    )

    dry = run_work_intake_historical_prune(workspace_root=ws, core_root=repo_root, dry_run=True, trigger="contract")
    if str(dry.get("status") or "") != "WOULD_WRITE":
        raise SystemExit("work_intake_historical_prune_contract_test failed: dry-run status")
    if int(dry.get("candidates_count") or 0) != 1:
        raise SystemExit("work_intake_historical_prune_contract_test failed: dry-run candidates_count")
    if int(dry.get("archived_count") or 0) != 0:
        raise SystemExit("work_intake_historical_prune_contract_test failed: dry-run archived_count")

    apply_res = run_work_intake_historical_prune(workspace_root=ws, core_root=repo_root, dry_run=False, trigger="contract")
    if str(apply_res.get("status") or "") != "OK":
        raise SystemExit("work_intake_historical_prune_contract_test failed: apply status")
    if int(apply_res.get("archived_count") or 0) != 1:
        raise SystemExit("work_intake_historical_prune_contract_test failed: apply archived_count")

    after = _load_json(jobs_index_path)
    jobs = after.get("jobs") if isinstance(after, dict) else None
    if not isinstance(jobs, list):
        raise SystemExit("work_intake_historical_prune_contract_test failed: jobs missing")
    by_id = {str(j.get("job_id") or ""): j for j in jobs if isinstance(j, dict)}
    archived = by_id.get("job-merge-skip-old")
    if not isinstance(archived, dict):
        raise SystemExit("work_intake_historical_prune_contract_test failed: archived job missing")
    if str(archived.get("status") or "") != "ARCHIVED":
        raise SystemExit("work_intake_historical_prune_contract_test failed: archived status mismatch")
    if str(archived.get("archived_reason") or "") != "SUPERSEDED_BY_PASS":
        raise SystemExit("work_intake_historical_prune_contract_test failed: archived_reason mismatch")

    counts = after.get("counts") if isinstance(after.get("counts"), dict) else {}
    expected = {"total": 2, "pass": 1, "fail": 1, "skip": 0}
    for key, val in expected.items():
        if int(counts.get(key, -1)) != val:
            raise SystemExit(f"work_intake_historical_prune_contract_test failed: counts[{key}]={counts.get(key)}")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
