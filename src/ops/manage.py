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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
