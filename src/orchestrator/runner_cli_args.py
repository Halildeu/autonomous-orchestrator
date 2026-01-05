from __future__ import annotations

import argparse

from src.orchestrator import budget_runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--envelope", help="Path to a request envelope JSON.")
    mode.add_argument("--resume", help="Path to an evidence/<run_id> directory to resume.")
    mode.add_argument("--replay", help="Path to an evidence/<run_id> directory to replay.")
    ap.add_argument("--approve", type=budget_runtime.parse_bool, default=False)
    ap.add_argument("--force-new-run", type=budget_runtime.parse_bool, default=False)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="evidence")
    return ap.parse_args(argv)
