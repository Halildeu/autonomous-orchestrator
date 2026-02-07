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
            "intake_id": "INT-1",
            "bucket": "TICKET",
            "priority": "P2",
            "severity": "S2",
            "autopilot_allowed": True,
            "autopilot_selected": True,
            "suggested_extension": ["PRJ-AIRUNNER"],
            "source_type": "JOB_STATUS",
            "source_ref": "SMOKE_FULL|TICKET|abc",
            "status": "OPEN",
        },
        {
            "intake_id": "INT-2",
            "bucket": "TICKET",
            "priority": "P1",
            "severity": "S1",
            "autopilot_allowed": True,
            "autopilot_selected": False,
            "suggested_extension": ["PRJ-GITHUB-OPS"],
            "source_type": "GITHUB_OPS",
            "source_ref": "SMOKE_FULL|FAIL|demo",
            "status": "OPEN",
        },
    ]

    plan = plan_auto_mode_dispatch(items=items, policy=policy, workspace_root=repo_root)
    if plan.get("candidates", [])[0].get("intake_id") != "INT-2":
        raise SystemExit("auto_mode_dispatch_contract_test failed: candidate ordering")
    if "INT-1" not in plan.get("selected_ids", []):
        raise SystemExit("auto_mode_dispatch_contract_test failed: selected_ids missing")
    jobs = plan.get("job_candidates", [])
    if not jobs or jobs[0].get("job_kind") != "SMOKE_FULL":
        raise SystemExit("auto_mode_dispatch_contract_test failed: job_kind inference")

    print(json.dumps({"status": "OK", "selected_ids": plan.get("selected_ids")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
