from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    from src.ops.commands.status_cmds import register_status_subcommands
    from src.ops.commands.hygiene_cmds import register_hygiene_subcommands
    from src.ops.commands.debt_cmds import register_debt_subcommands
    from src.ops.commands.roadmap_cmds import register_roadmap_subcommands
    from src.ops.ops_capabilities import register_ops_capabilities_subcommand
    from src.ops.workspace_find import register_workspace_find_subcommand
    from src.ops.closeout_write import register_closeout_write_subcommand
    from src.ops.roadmap_resolve import register_roadmap_resolve_subcommand
    from src.ops.roadmap_seed import register_roadmap_seed_subcommand
    from src.ops.roadmap_state_sync import register_roadmap_state_sync_subcommand
    from src.ops.test_run import register_test_run_subcommand
    from src.prj_github_ops.smoke_fast_marker_extract import (
        register_smoke_fast_marker_extract_subcommand,
    )
    from src.ops.github_ops_index_lock_local import (
        register_github_ops_index_lock_clear_local_subcommand,
    )
    from src.ops.operability_heartbeat_reconcile import (
        register_operability_heartbeat_reconcile_subcommand,
    )
    from src.ops.index_lock_file_diagnostics import (
        register_index_lock_file_diagnostics_subcommand,
    )
    from src.ops.index_lock_repo_root_reconcile import (
        register_index_lock_repo_root_reconcile_subcommand,
    )
    from src.ops.heartbeat_checker_pinpoint import (
        register_heartbeat_checker_pinpoint_subcommand,
    )
    from src.ops.policy_rule_extract import (
        register_policy_rule_extract_subcommand,
    )
    from src.ops.eval_runner_heartbeat_pinpoint import (
        register_eval_runner_heartbeat_pinpoint_subcommand,
    )
    from src.ops.eval_runner_heartbeat_select import (
        register_eval_runner_heartbeat_select_subcommand,
    )
    from src.ops.policy_thresholds_map import (
        register_policy_thresholds_map_subcommand,
    )
    from src.ops.heartbeat_rule_source_diff import (
        register_heartbeat_rule_source_diff_subcommand,
    )
    from src.ops.commands.enforcement_cmds import register_enforcement_subcommands
    from src.ops.commands.vendor_pack_verify import register_vendor_pack_verify_subcommand

    register_status_subcommands(sub)
    register_hygiene_subcommands(sub)
    register_debt_subcommands(sub)
    register_roadmap_subcommands(sub)
    register_ops_capabilities_subcommand(sub)
    register_workspace_find_subcommand(sub)
    register_closeout_write_subcommand(sub)
    register_roadmap_resolve_subcommand(sub)
    register_roadmap_seed_subcommand(sub)
    register_roadmap_state_sync_subcommand(sub)
    register_test_run_subcommand(sub)
    register_smoke_fast_marker_extract_subcommand(sub)
    register_github_ops_index_lock_clear_local_subcommand(sub)
    register_operability_heartbeat_reconcile_subcommand(sub)
    register_index_lock_file_diagnostics_subcommand(sub)
    register_index_lock_repo_root_reconcile_subcommand(sub)
    register_heartbeat_checker_pinpoint_subcommand(sub)
    register_policy_rule_extract_subcommand(sub)
    register_eval_runner_heartbeat_pinpoint_subcommand(sub)
    register_eval_runner_heartbeat_select_subcommand(sub)
    register_policy_thresholds_map_subcommand(sub)
    register_heartbeat_rule_source_diff_subcommand(sub)
    register_enforcement_subcommands(sub)
    register_vendor_pack_verify_subcommand(sub)

    return parser


def _normalize_subcommand(argv: list[str], parser: argparse.ArgumentParser) -> list[str]:
    if not argv:
        return argv
    cmd = argv[0]
    if not isinstance(cmd, str):
        return argv
    if cmd.startswith("airrunner-"):
        cmd = "airunner-" + cmd[len("airrunner-") :]
        argv[0] = cmd
    sub_action = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and action.dest == "command":
            sub_action = action
            break
    if sub_action is None:
        return argv
    try:
        cmd_bytes = cmd.encode("utf-8")
    except Exception:
        return argv
    for key in sub_action.choices.keys():
        if not isinstance(key, str):
            continue
        try:
            if key.encode("utf-8") == cmd_bytes:
                argv[0] = key
                break
        except Exception:
            continue
    return argv


def main(argv: list[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    if argv_list and argv_list[0] == "airrunner-proof-bundle":
        ap = argparse.ArgumentParser(prog="airrunner-proof-bundle")
        ap.add_argument("--workspace-root", required=True)
        ap.add_argument("--chat", default="false")
        args = ap.parse_args(argv_list[1:])
        from src.ops.commands.extension_cmds import cmd_airunner_proof_bundle

        return int(cmd_airunner_proof_bundle(args))

    parser = build_parser()
    normalized = _normalize_subcommand(argv_list, parser)
    args = parser.parse_args(normalized)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
