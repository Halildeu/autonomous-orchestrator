from __future__ import annotations

import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.auto_loop import _compute_pr_merge_promotion_plan

    # --- Case 1: not needed ---
    plan = _compute_pr_merge_promotion_plan(
        github_ops_report={
            "git_state": {"dirty_tree": False, "ahead": 0, "behind": 0, "index_lock": False},
            "live_gate": {"enabled": False},
        }
    )
    _assert(plan.get("needed") is False, "expected needed=false")
    _assert(plan.get("should_run") is False, "expected should_run=false")
    _assert(plan.get("skip_reason") == "NOT_NEEDED", "expected NOT_NEEDED")

    # --- Case 2: behind remote (fail-closed) ---
    plan = _compute_pr_merge_promotion_plan(
        github_ops_report={
            "git_state": {"dirty_tree": True, "ahead": 0, "behind": 1, "index_lock": False},
            "live_gate": {"enabled": True},
        }
    )
    _assert(plan.get("needed") is True, "expected needed=true for dirty_tree")
    _assert(plan.get("should_run") is False, "expected should_run=false when behind>0")
    _assert(plan.get("skip_reason") == "BEHIND_REMOTE", "expected BEHIND_REMOTE")

    # --- Case 3: index.lock present (fail-closed) ---
    plan = _compute_pr_merge_promotion_plan(
        github_ops_report={
            "git_state": {"dirty_tree": True, "ahead": 0, "behind": 0, "index_lock": True},
            "live_gate": {"enabled": True},
        }
    )
    _assert(plan.get("needed") is True, "expected needed=true for dirty_tree")
    _assert(plan.get("should_run") is False, "expected should_run=false when index_lock present")
    _assert(plan.get("skip_reason") == "GIT_INDEX_LOCK_PRESENT", "expected GIT_INDEX_LOCK_PRESENT")

    # --- Case 4: gate disabled (fail-closed) ---
    plan = _compute_pr_merge_promotion_plan(
        github_ops_report={
            "git_state": {"dirty_tree": True, "ahead": 0, "behind": 0, "index_lock": False},
            "live_gate": {
                "enabled": False,
                "network_enabled": False,
                "env_flag_set": False,
                "env_key_present": False,
            },
        }
    )
    _assert(plan.get("needed") is True, "expected needed=true for dirty_tree")
    _assert(plan.get("should_run") is False, "expected should_run=false when gate disabled")
    _assert(plan.get("skip_reason") == "GITHUB_OPS_GATE_BLOCKED", "expected GITHUB_OPS_GATE_BLOCKED")

    # --- Case 5: should run ---
    plan = _compute_pr_merge_promotion_plan(
        github_ops_report={
            "git_state": {"dirty_tree": True, "ahead": 0, "behind": 0, "index_lock": False},
            "live_gate": {"enabled": True},
        }
    )
    _assert(plan.get("needed") is True, "expected needed=true for dirty_tree")
    _assert(plan.get("should_run") is True, "expected should_run=true when gate enabled and safe")
    _assert(plan.get("skip_reason") is None, "expected skip_reason=None when should_run=true")

    print("OK")


if __name__ == "__main__":
    main()

