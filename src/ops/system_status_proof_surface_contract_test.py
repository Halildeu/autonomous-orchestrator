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

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_proof_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    proof_payload = {
        "version": "v1",
        "workspace_root": str(ws),
        "baseline_path": ".cache/reports/airunner_baseline.v1.json",
        "run_path": ".cache/reports/airunner_run.v1.json",
        "deltas_path": ".cache/reports/airunner_deltas.v1.json",
        "tick1_path": ".cache/reports/airunner_tick_1.v1.json",
        "tick2_path": ".cache/reports/airunner_tick_2.v1.json",
        "proof_path": ".cache/reports/github_ops_no_wait_proof.v2.json",
        "seed_audit_path": ".cache/reports/airunner_seed_audit.v1.json",
        "poll_only_observed": True,
        "start_only_observed": True,
        "tick1_ops": ["airunner-jobs-poll"],
        "tick2_ops": ["github-ops-job-start"],
        "jobs_polled_delta": 1,
        "jobs_started_delta": 1,
        "intake_new_items_delta": 0,
        "suppressed_delta": 0,
    }
    _write_json(ws / ".cache" / "reports" / "airunner_proof_bundle.v1.json", proof_payload)

    policy = _load_policy(repo_root, ws)
    report = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = report.get("sections") if isinstance(report, dict) else {}
    proof = sections.get("airunner_proof") if isinstance(sections, dict) else None
    if not isinstance(proof, dict):
        raise SystemExit("system_status_proof_surface_contract_test failed: missing section")
    if proof.get("status") != "OK":
        raise SystemExit("system_status_proof_surface_contract_test failed: status not OK")
    if proof.get("last_proof_bundle_path") != ".cache/reports/airunner_proof_bundle.v1.json":
        raise SystemExit("system_status_proof_surface_contract_test failed: path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
