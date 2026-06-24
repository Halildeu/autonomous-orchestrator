from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.auto_mode_dispatch import _policy_defaults, plan_auto_mode_dispatch

    policy = _policy_defaults()
    policy["enabled"] = True
    policy["mode"] = "mixed"

    items = [
        {
            "intake_id": "INT-GH-1",
            "bucket": "OPS",
            "priority": "P3",
            "severity": "S3",
            "autopilot_allowed": False,
            "autopilot_selected": False,
            "suggested_extension": ["PRJ-GITHUB-OPS"],
            "source_type": "GITHUB_OPS",
            "source_ref": "github_ops:live_gate_disabled",
            "title": "github_ops live gate disabled",
            "status": "OPEN",
        },
        {
            "intake_id": "INT-BOARD-1",
            "bucket": "TICKET",
            "priority": "P3",
            "severity": "S3",
            "autopilot_allowed": True,
            "autopilot_selected": True,
            "suggested_extension": ["PRJ-AIRUNNER"],
            "source_type": "MANUAL_REQUEST",
            "source_ref": "board-governance-implementation-boundary",
            "title": "board-governance-implementation-boundary / github-ops",
            "status": "OPEN",
        },
    ]

    plan = plan_auto_mode_dispatch(items=items, policy=policy, workspace_root=repo_root)

    jobs = plan.get("job_candidates") if isinstance(plan.get("job_candidates"), list) else []
    gh_jobs = [job for job in jobs if isinstance(job, dict) and job.get("intake_id") == "INT-GH-1"]
    if not gh_jobs:
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: github job candidate missing")
    gh_boundary = gh_jobs[0].get("boundary_decision") if isinstance(gh_jobs[0].get("boundary_decision"), dict) else {}
    if gh_boundary.get("boundary_id") != "AIRUNNER-BOARD-GITHUB-OPS-BOUNDARY-v1":
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: github boundary missing")
    if gh_boundary.get("autonomous_mutation_allowed") is not False:
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: github mutation should be blocked")
    if gh_boundary.get("dry_run_required") is not True:
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: dry-run should be required")
    blocked = set(gh_boundary.get("blocked_reasons") or [])
    if not {"GITHUB_OPS_LIVE_GATE_REQUIRED", "NETWORK_LIVE_DECISION_REQUIRED"}.issubset(blocked):
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: live gates not recorded")

    if "INT-BOARD-1" in set(plan.get("selected_ids") or []):
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: manual boundary request selected")
    planned = plan.get("plan_candidates") if isinstance(plan.get("plan_candidates"), list) else []
    manual = [item for item in planned if isinstance(item, dict) and item.get("intake_id") == "INT-BOARD-1"]
    if not manual:
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: manual boundary plan missing")
    manual_boundary = manual[0].get("boundary_decision") if isinstance(manual[0].get("boundary_decision"), dict) else {}
    if manual_boundary.get("requires_operator_approval") is not True:
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: operator approval not required")
    forbidden = set(manual_boundary.get("forbidden_autonomous_actions") or [])
    if not {"projectv2_apply", "issue_close", "done_transition"}.issubset(forbidden):
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: forbidden actions incomplete")
    evidence = set(manual_boundary.get("required_evidence_fields") or [])
    if not {"boundary_decision", "does_not_prove", "live_gate", "network_gate"}.issubset(evidence):
        raise SystemExit("airrunner_board_github_boundary_contract_test failed: evidence fields incomplete")

    print(
        json.dumps(
            {
                "status": "OK",
                "job_boundary": gh_boundary.get("boundary_id"),
                "manual_plan_only": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
