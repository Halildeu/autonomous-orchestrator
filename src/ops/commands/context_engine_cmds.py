"""Context Engine v2 CLI commands (R8: separate module to avoid budget overflow).

Commands:
  compile-context    — Compile unified enforcement context for a target path
  bootstrap-gate     — Run full bootstrap gate (health + profile + grace)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def register_context_engine_subcommands(sub: argparse._SubParsersAction) -> None:
    """Register context engine commands in manage.py dispatch table."""

    # compile-context
    p_compile = sub.add_parser(
        "compile-context",
        help="Compile unified enforcement context for a target path",
    )
    p_compile.add_argument("--workspace-root", required=True)
    p_compile.add_argument("--target-path", required=True)
    p_compile.add_argument("--agent-id", default="claude", choices=["claude", "codex", "antigravity"])
    p_compile.set_defaults(func=_cmd_compile_context)

    # bootstrap-gate
    p_gate = sub.add_parser(
        "bootstrap-gate",
        help="Run full bootstrap gate (health + profile + grace mode)",
    )
    p_gate.add_argument("--workspace-root", required=True)
    p_gate.add_argument("--repo-root", default=".")
    p_gate.add_argument("--grace-invocations", type=int, default=2)
    p_gate.set_defaults(func=_cmd_bootstrap_gate)


def _cmd_compile_context(args: argparse.Namespace) -> int:
    from src.ops.context_compiler import compile_enforcement_context

    ws = Path(args.workspace_root).expanduser().resolve()
    result = compile_enforcement_context(
        workspace_root=ws,
        target_path=args.target_path,
        agent_id=args.agent_id,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_bootstrap_gate(args: argparse.Namespace) -> int:
    from ci.check_context_bootstrap import run_bootstrap_gate

    repo = Path(args.repo_root).resolve()
    ws = Path(args.workspace_root).expanduser().resolve()
    result = run_bootstrap_gate(
        repo_root=repo,
        workspace_root=ws,
        grace_invocations=args.grace_invocations,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["gate_result"] == "BLOCKED":
        return 1
    return 0
