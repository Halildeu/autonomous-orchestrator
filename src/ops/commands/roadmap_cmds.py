from __future__ import annotations

import argparse


def register_roadmap_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    from src.ops.roadmap_cli import register_roadmap_subcommands as _register_roadmap
    from src.ops.session_cli import register_session_subcommands as _register_session
    from src.ops.artifact_cli import register_artifact_subcommands as _register_artifact
    from src.ops.benchmark_cli import register_benchmark_subcommands as _register_benchmark

    _register_roadmap(parent)
    _register_session(parent)
    _register_artifact(parent)
    _register_benchmark(parent)
