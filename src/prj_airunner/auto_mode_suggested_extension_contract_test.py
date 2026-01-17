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
    policy["mode"] = "suggested_only"

    items = [
        {
            "intake_id": "INT-ALPHA",
            "bucket": "TICKET",
            "priority": "P2",
            "severity": "S2",
            "autopilot_allowed": False,
            "autopilot_selected": False,
            "suggested_extension": ["PRJ-GITHUB-OPS"],
            "source_type": "GITHUB_OPS",
            "source_ref": "SMOKE_FULL|FAIL|demo",
            "status": "OPEN",
        }
    ]

    plan = plan_auto_mode_dispatch(items=items, policy=policy, workspace_root=repo_root)
    candidates = plan.get("candidates", [])
    if not candidates:
        raise SystemExit("auto_mode_suggested_extension_contract_test failed: no candidates")
    if candidates[0].get("selection_reason") != "suggested_extension":
        raise SystemExit("auto_mode_suggested_extension_contract_test failed: selection reason")
    jobs = plan.get("job_candidates", [])
    if not jobs or jobs[0].get("extension_id") != "PRJ-GITHUB-OPS":
        raise SystemExit("auto_mode_suggested_extension_contract_test failed: job candidate")

    print(json.dumps({"status": "OK", "candidates": len(candidates)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
