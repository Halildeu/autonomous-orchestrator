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

    register_status_subcommands(sub)
    register_hygiene_subcommands(sub)
    register_debt_subcommands(sub)
    register_roadmap_subcommands(sub)

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
