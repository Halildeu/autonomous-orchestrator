from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_enforcement_check(args: argparse.Namespace) -> int:
    root = repo_root()

    outdir_arg = str(args.outdir).strip() if args.outdir else ""
    if not outdir_arg:
        warn("FAIL error=OUTDIR_REQUIRED")
        return 2

    outdir = Path(outdir_arg)
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()

    ruleset_arg = str(args.ruleset).strip() if args.ruleset else ""
    if not ruleset_arg:
        ruleset_arg = "extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules"
    ruleset = Path(ruleset_arg)
    ruleset = (root / ruleset).resolve() if not ruleset.is_absolute() else ruleset.resolve()

    profile = str(args.profile).strip().lower() if args.profile else "default"
    if profile not in {"default", "strict"}:
        warn("FAIL error=INVALID_PROFILE")
        return 2

    baseline = str(args.baseline).strip() if args.baseline else ""
    intake_id = str(args.intake_id).strip() if getattr(args, "intake_id", None) else ""

    try:
        chat = parse_reaper_bool(str(args.chat))
    except ValueError:
        warn("FAIL error=INVALID_CHAT_BOOL")
        return 2

    from src.ops.commands.enforcement_check import run_enforcement_check

    result = run_enforcement_check(
        outdir=outdir,
        ruleset=ruleset,
        profile=profile,
        baseline=baseline,
        intake_id=intake_id,
        chat=bool(chat),
    )

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    status = result.get("status") if isinstance(result, dict) else None
    return 0 if status in {"OK", "WARN"} else 2


def register_enforcement_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap = parent.add_parser(
        "enforcement-check",
        help="Run enforcement checks and emit the canonical enforcement-check contract (offline-first).",
    )
    ap.add_argument(
        "--ruleset",
        default="extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules",
        help="Semgrep ruleset path (default: extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules).",
    )
    ap.add_argument("--profile", default="default", help="default|strict (default: default).")
    ap.add_argument("--baseline", default="", help="Optional baseline ref (e.g., git:HEAD~1) for delta scans.")
    ap.add_argument("--outdir", required=True, help="Output evidence directory (workspace path).")
    ap.add_argument("--intake-id", default="", help="Optional intake id for contract output (default: UNKNOWN).")
    ap.add_argument("--chat", default="false", help="true|false (default: false).")
    ap.set_defaults(func=cmd_enforcement_check)

