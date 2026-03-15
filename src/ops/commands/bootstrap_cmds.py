from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import repo_root, resolve_workspace_root_arg, warn


def cmd_bootstrap_check(args: argparse.Namespace) -> int:
    root = repo_root()
    raw = str(getattr(args, "workspace_root", "") or "").strip()
    if not raw:
        raw = "."
    ws = resolve_workspace_root_arg(root, raw, prefer_customer_workspace=True)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2

    from ci.check_context_bootstrap import run_bootstrap_check

    result = run_bootstrap_check(
        repo_root=root,
        workspace_root=ws,
        freshness_threshold=int(getattr(args, "freshness_threshold", 86400)),
    )
    chat = str(getattr(args, "chat", "false")).strip().lower() in {"true", "1", "yes"}
    if chat:
        status = result.get("status", "FAIL")
        issues = result.get("issues", [])
        lines = [f"RESULT status={status}"]
        for tier in result.get("tiers", []):
            lines.append(f"  tier={tier.get('tier')} name={tier.get('name')} status={tier.get('status')}")
        for iss in issues:
            lines.append(f"  issue: {iss}")
        print("\n".join(lines))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))

    return 0 if result.get("status") == "OK" else 2


def register_bootstrap_subcommands(
    parent: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    ap = parent.add_parser("bootstrap-check", help="Validate context bootstrap tiers.")
    ap.add_argument("--workspace-root", default=".")
    ap.add_argument("--freshness-threshold", type=int, default=86400, help="Max age in seconds for freshness check")
    ap.add_argument("--chat", default="false")
    ap.set_defaults(func=cmd_bootstrap_check)
