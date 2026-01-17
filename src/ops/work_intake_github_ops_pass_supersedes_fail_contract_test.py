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

    ws = repo_root / ".cache" / "ws_work_intake_github_ops_pass_supersedes_fail"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    t1 = "2026-01-13T00:49:17Z"
    t2 = "2026-01-16T00:49:17Z"

    _write_json(
        ws / ".cache" / "reports" / "github_ops_report.v1.json",
        {
            "version": "v1",
            "generated_at": t2,
            "workspace_root": str(ws),
            "status": "OK",
            "signals": [],
            "jobs_index_path": ".cache/github_ops/jobs_index.v1.json",
        },
    )

    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {
            "version": "v1",
            "generated_at": t2,
            "workspace_root": str(ws),
            "status": "OK",
            "jobs": [
                {
                    "version": "v1",
                    "job_id": "job-fail-1",
                    "kind": "SMOKE_FULL",
                    "status": "FAIL",
                    "failure_class": "OTHER",
                    "skip_reason": "",
                    "signature_hash": "sig-fail",
                    "created_at": t1,
                    "started_at": t1,
                    "last_poll_at": t1,
                    "updated_at": t1,
                    "evidence_paths": [],
                    "result_paths": [],
                    "notes": [],
                },
                {
                    "version": "v1",
                    "job_id": "job-pass-2",
                    "kind": "SMOKE_FULL",
                    "status": "PASS",
                    "failure_class": "PASS",
                    "skip_reason": "",
                    "signature_hash": "sig-pass",
                    "created_at": t2,
                    "started_at": t2,
                    "last_poll_at": t2,
                    "updated_at": t2,
                    "evidence_paths": [],
                    "result_paths": [],
                    "notes": [],
                },
            ],
            "counts": {"total": 2, "queued": 0, "running": 0, "pass": 1, "fail": 1, "timeout": 0, "killed": 0, "skip": 0},
            "notes": [],
        },
    )

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_github_ops_pass_supersedes_fail_contract_test failed: build status")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("work_intake_github_ops_pass_supersedes_fail_contract_test failed: work intake missing")

    obj = json.loads(intake_path.read_text(encoding="utf-8"))
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_github_ops_pass_supersedes_fail_contract_test failed: items missing")

    gh_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "GITHUB_OPS"]
    smoke_full = [i for i in gh_items if str(i.get("source_ref") or "").startswith("github_ops_sig:SMOKE_FULL|")]
    if len(smoke_full) != 1:
        raise SystemExit(
            f"work_intake_github_ops_pass_supersedes_fail_contract_test failed: expected 1 SMOKE_FULL item, got {len(smoke_full)}"
        )
    if str(smoke_full[0].get("status") or "") != "DONE":
        raise SystemExit("work_intake_github_ops_pass_supersedes_fail_contract_test failed: PASS item must be DONE")
    if "|FAIL|" in str(smoke_full[0].get("source_ref") or ""):
        raise SystemExit("work_intake_github_ops_pass_supersedes_fail_contract_test failed: FAIL must be pruned by PASS")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

