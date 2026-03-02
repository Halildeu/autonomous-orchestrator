from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"maintenance_cmds_refactor_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import src.ops.commands.maintenance_cmds as mod

    original = {
        "check": mod._cmd_work_intake_check_runtime,
        "exec": mod._cmd_work_intake_exec_ticket_runtime,
        "build": mod._cmd_decision_inbox_build_runtime,
        "apply": mod._cmd_decision_apply_runtime,
        "seed": mod._cmd_decision_seed_runtime,
    }

    mod._cmd_work_intake_check_runtime = lambda args: 11
    mod._cmd_work_intake_exec_ticket_runtime = lambda args: 12
    mod._cmd_decision_inbox_build_runtime = lambda args: 13
    mod._cmd_decision_apply_runtime = lambda args: 14
    mod._cmd_decision_seed_runtime = lambda args: 15

    try:
        _must(mod.cmd_work_intake_check(argparse.Namespace()) == 11, "work_intake_check wrapper failed")
        _must(mod.cmd_work_intake_exec_ticket(argparse.Namespace()) == 12, "work_intake_exec wrapper failed")
        _must(mod.cmd_decision_inbox_build(argparse.Namespace()) == 13, "decision_inbox_build wrapper failed")
        _must(mod.cmd_decision_apply(argparse.Namespace()) == 14, "decision_apply wrapper failed")
        _must(mod.cmd_decision_seed(argparse.Namespace()) == 15, "decision_seed wrapper failed")
    finally:
        mod._cmd_work_intake_check_runtime = original["check"]
        mod._cmd_work_intake_exec_ticket_runtime = original["exec"]
        mod._cmd_decision_inbox_build_runtime = original["build"]
        mod._cmd_decision_apply_runtime = original["apply"]
        mod._cmd_decision_seed_runtime = original["seed"]

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
