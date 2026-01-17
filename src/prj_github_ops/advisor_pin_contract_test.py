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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _advisor_payload(workspace_root: Path) -> dict:
    return {
        "version": "v1",
        "generated_at": "2026-01-01T00:00:00Z",
        "workspace_root": str(workspace_root),
        "inputs_summary": {
            "public_candidates_present": False,
            "run_index_present": False,
            "dlq_index_present": False,
            "actions_present": False,
            "counts": {"candidates": 0, "runs": 0, "dlq": 0, "actions": 0},
        },
        "suggestions": [
            {
                "id": "ADVISOR_PIN_TEST",
                "kind": "QUALITY",
                "title": "Advisor pin test",
                "details": "Pinned advisor artifact for triage contract.",
                "confidence": 0.0,
                "evidence_refs": ["ADVISOR_PIN_TEST"],
                "recommended_action": "Inspect advisor output wiring.",
            }
        ],
        "safety": {"status": "WARN", "notes": ["ADVISOR_PIN_TEST"]},
    }


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.smoke_full_triage import run_smoke_full_triage

    job_id = "contract-smoke-full-advisor-pin"
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)

        job_dir = ws_root / ".cache" / "github_ops" / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        _write_json(job_dir / "rc.json", {"rc": 1})
        (job_dir / "stderr.log").write_text(
            "Smoke test failed: M7 apply must write advisor suggestions: "
            f"{ws_root}/.cache/learning/advisor_suggestions.v1.json\n",
            encoding="utf-8",
        )
        (job_dir / "stdout.log").write_text("", encoding="utf-8")

        artifact_path = (
            ws_root
            / ".cache"
            / "reports"
            / "jobs"
            / f"smoke_full_{job_id}"
            / "advisor_suggestions.v1.json"
        )
        _write_json(artifact_path, _advisor_payload(ws_root))

        report_path = (
            ws_root
            / ".cache"
            / "reports"
            / "github_ops_jobs"
            / f"github_ops_job_{job_id}.v1.json"
        )
        _write_json(
            report_path,
            {
                "job_id": job_id,
                "status": "FAIL",
                "kind": "SMOKE_FULL",
                "failure_class": "DEMO_ADVISOR_SUGGESTIONS_MISSING",
                "workspace_root": str(ws_root),
                "result_paths": [
                    str(Path(".cache") / "github_ops" / "jobs" / job_id / "stderr.log"),
                    str(Path(".cache") / "github_ops" / "jobs" / job_id / "stdout.log"),
                    str(Path(".cache") / "github_ops" / "jobs" / job_id / "rc.json"),
                ],
            },
        )

        run_smoke_full_triage(workspace_root=ws_root, job_id=job_id, detail=True)

        triage_path = ws_root / ".cache" / "reports" / "smoke_full_triage.v1.json"
        if not triage_path.exists():
            raise SystemExit("advisor_pin_contract_test failed: triage missing")
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        advisor = triage.get("advisor_suggestions") if isinstance(triage, dict) else None
        if not isinstance(advisor, dict):
            raise SystemExit("advisor_pin_contract_test failed: advisor field missing")
        if advisor.get("job_artifact_exists") is not True or advisor.get("job_artifact_json_valid") is not True:
            raise SystemExit("advisor_pin_contract_test failed: job artifact flags invalid")
        if triage.get("recommended_class") == "DEMO_ADVISOR_SUGGESTIONS_MISSING":
            raise SystemExit("advisor_pin_contract_test failed: missing class not overridden")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
