from __future__ import annotations

import argparse


def register_status_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    from src.ops.commands.list_cmds import register_list_subcommands as _register_list
    from src.ops.commands.maintenance_cmds import register_maintenance_subcommands as _register_maintenance

    _register_list(parent)
    _register_maintenance(parent)
