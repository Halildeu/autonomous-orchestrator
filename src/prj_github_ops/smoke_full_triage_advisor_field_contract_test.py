from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.smoke_full_triage import run_smoke_full_triage

    job_id = "contract-smoke-full-advisor"
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)

        expected_path = ws_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
        expected_payload = {
            "version": "v1",
            "generated_at": "2026-01-01T00:00:00Z",
            "workspace_root": str(ws_root),
            "inputs_summary": {
                "public_candidates_present": False,
                "run_index_present": False,
                "dlq_index_present": False,
                "actions_present": False,
                "counts": {"candidates": 0, "runs": 0, "dlq": 0, "actions": 0},
            },
            "suggestions": [],
            "safety": {"status": "WARN", "notes": []},
        }
        _write_json(expected_path, expected_payload)

        job_dir = ws_root / ".cache" / "github_ops" / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = job_dir / "stderr.log"
        stdout_path = job_dir / "stdout.log"
        rc_path = job_dir / "rc.json"
        stderr_path.write_text(
            f"Smoke test failed: M7 apply must write advisor suggestions: {expected_path}\n", encoding="utf-8"
        )
        stdout_path.write_text("", encoding="utf-8")
        _write_json(rc_path, {"rc": 1})

        job_report = {
            "job_id": job_id,
            "status": "FAIL",
            "kind": "SMOKE_FULL",
            "failure_class": "DEMO_ADVISOR_SUGGESTIONS_MISSING",
            "result_paths": [
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "stderr.log"),
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "stdout.log"),
                str(Path(".cache") / "github_ops" / "jobs" / job_id / "rc.json"),
            ],
        }
        report_path = ws_root / ".cache" / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json"
        _write_json(report_path, job_report)

        run_smoke_full_triage(workspace_root=ws_root, job_id=job_id, detail=True)

        triage_path = ws_root / ".cache" / "reports" / "smoke_full_triage.v1.json"
        if not triage_path.exists():
            raise SystemExit("smoke_full_triage_advisor_field_contract_test failed: triage missing")
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        advisor = triage.get("advisor_suggestions") if isinstance(triage, dict) else None
        if not isinstance(advisor, dict):
            raise SystemExit("smoke_full_triage_advisor_field_contract_test failed: advisor field missing")
        if advisor.get("expected_path") != str(expected_path):
            raise SystemExit("smoke_full_triage_advisor_field_contract_test failed: expected_path mismatch")
        if advisor.get("exists") is not True or advisor.get("json_valid") is not True:
            raise SystemExit("smoke_full_triage_advisor_field_contract_test failed: advisor flags invalid")

        advisor_report = ws_root / ".cache" / "reports" / "advisor_expected_paths.v1.json"
        if not advisor_report.exists():
            raise SystemExit("smoke_full_triage_advisor_field_contract_test failed: advisor report missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
