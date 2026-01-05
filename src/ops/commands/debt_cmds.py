from __future__ import annotations

import argparse


def register_debt_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    from src.ops.commands.integration_cmds import register_integration_subcommands as _register_integration

    _register_integration(parent)
