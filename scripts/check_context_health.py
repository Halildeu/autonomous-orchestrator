#!/usr/bin/env python3
"""Lightweight context health check for managed repos.

Runs in CI gate (non-blocking). Reports context health score without
requiring the full orchestrator runtime.

Usage:
  python3 scripts/check_context_health.py --workspace-root .cache/ws_customer_default
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check context health for a managed repo workspace.")
    parser.add_argument("--workspace-root", required=True, help="Workspace root path.")
    parser.add_argument("--blocking", default="false", help="true|false — if true, exit 2 on FAIL.")
    args = parser.parse_args(argv)

    ws = Path(str(args.workspace_root)).expanduser().resolve()
    blocking = str(args.blocking).strip().lower() == "true"

    if not ws.exists():
        print(json.dumps({"status": "SKIP", "score": 0, "grade": "F", "reason": "workspace_not_found"}, sort_keys=True))
        return 0

    try:
        from src.benchmark.eval_runner_runtime import _compute_context_health_lens

        health = _compute_context_health_lens(workspace_root=ws, lenses_policy={})
        score_100 = int(float(health.get("score", 0)) * 100)
        grade = "A" if score_100 >= 90 else "B" if score_100 >= 80 else "C" if score_100 >= 70 else "D" if score_100 >= 50 else "F"

        result = {
            "status": health.get("status", "UNKNOWN"),
            "score": score_100,
            "grade": grade,
            "blocking": blocking and health.get("status") == "FAIL",
            "components": health.get("components", {}),
            "reasons": health.get("reasons", []),
        }
        print(json.dumps(result, sort_keys=True))

        if blocking and health.get("status") == "FAIL":
            return 2
        return 0

    except Exception as e:
        print(json.dumps({"status": "ERROR", "score": 0, "grade": "F", "error": str(e)[:200]}, sort_keys=True))
        return 0  # Non-blocking even on error


if __name__ == "__main__":
    raise SystemExit(main())
