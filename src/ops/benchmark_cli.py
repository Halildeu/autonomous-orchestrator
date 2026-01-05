from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_benchmark_assess(args: argparse.Namespace) -> int:
    try:
        dry_run = bool(parse_reaper_bool(str(args.dry_run)))
    except Exception:
        print(json.dumps({"status": "FAIL", "error": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    workspace_root = Path(str(args.workspace_root)).resolve()
    try:
        from src.benchmark.assessment_runner import run_assessment
        payload = run_assessment(workspace_root=workspace_root, dry_run=dry_run)
    except Exception as e:
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "BENCHMARK_INTERNAL_ERROR", "message": str(e)[:200]},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    status = payload.get("status") if isinstance(payload, dict) else None
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WOULD_WRITE", "SKIPPED"} else 2


def register_benchmark_subcommands(sub: argparse._SubParsersAction) -> None:
    ap = sub.add_parser("benchmark-assess", help="Run benchmark assessment (workspace-root outputs).")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap.set_defaults(func=cmd_benchmark_assess)
