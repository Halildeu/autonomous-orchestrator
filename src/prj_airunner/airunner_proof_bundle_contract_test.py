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
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_proof_bundle import run_airunner_proof_bundle

    ws = repo_root / ".cache" / "ws_airunner_proof_bundle_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(ws / ".cache" / "reports" / "airunner_baseline.v1.json", {"version": "v1", "notes": []})
    _write_json(ws / ".cache" / "reports" / "airunner_run.v1.json", {"version": "v1", "notes": []})
    _write_json(
        ws / ".cache" / "reports" / "airunner_deltas.v1.json",
        {"version": "v1", "jobs_polled_delta": 1, "jobs_started_delta": 1, "intake_new_items_delta": 0, "suppressed_delta": 0},
    )
    _write_json(ws / ".cache" / "reports" / "airunner_tick_1.v1.json", {"version": "v1", "ops_called": ["airunner-jobs-poll", "ui-snapshot-bundle"]})
    _write_json(ws / ".cache" / "reports" / "airunner_tick_2.v1.json", {"version": "v1", "ops_called": ["github-ops-job-start", "ui-snapshot-bundle"]})
    _write_json(
        ws / ".cache" / "reports" / "github_ops_no_wait_proof.v2.json",
        {
            "version": "v2",
            "poll_only_observed": True,
            "start_only_observed": True,
            "tick1": {"ops_called": ["airunner-jobs-poll", "ui-snapshot-bundle"]},
            "tick2": {"ops_called": ["github-ops-job-start", "ui-snapshot-bundle"]},
            "deltas": {"jobs_polled_delta": 1, "jobs_started_delta": 1, "intake_new_items_delta": 0, "suppressed_delta": 0},
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "airunner_seed_audit.v1.json",
        {
            "version": "v1",
            "seed_id": "seed-001",
            "kind": "SMOKE_FULL",
            "state": "queued",
            "created_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "notes": ["seeded=true"],
        },
    )

    res = run_airunner_proof_bundle(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "airunner_proof_bundle.v1.json"
    if not report_path.exists():
        raise SystemExit("airunner_proof_bundle_contract_test failed: report missing")

    bundle = _load_json(report_path)
    if bundle.get("poll_only_observed") is not True:
        raise SystemExit("airunner_proof_bundle_contract_test failed: poll_only_observed")
    if bundle.get("start_only_observed") is not True:
        raise SystemExit("airunner_proof_bundle_contract_test failed: start_only_observed")
    if bundle.get("tick1_ops") != ["airunner-jobs-poll", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_proof_bundle_contract_test failed: tick1_ops mismatch")
    if bundle.get("tick2_ops") != ["github-ops-job-start", "ui-snapshot-bundle"]:
        raise SystemExit("airunner_proof_bundle_contract_test failed: tick2_ops mismatch")
    if bundle.get("seed_audit_path") != ".cache/reports/airunner_seed_audit.v1.json":
        raise SystemExit("airunner_proof_bundle_contract_test failed: seed_audit_path mismatch")
    if res.get("status") != "OK":
        raise SystemExit("airunner_proof_bundle_contract_test failed: status not OK")

    print(json.dumps({"status": "OK", "report": res.get("report_path")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
