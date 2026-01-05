from __future__ import annotations

import argparse


def register_hygiene_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    from src.ops.commands.policy_cmds import register_policy_subcommands as _register_policy

    _register_policy(parent)
