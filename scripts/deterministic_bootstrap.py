#!/usr/bin/env python3
"""Deterministic bootstrap — maps user intent to fixed ops command sequence.

Reads policy_intent_runbook_registry.v1.json, matches trigger keywords,
and executes the runbook steps in order. No free-form interpretation.

Usage:
    python3 scripts/deterministic_bootstrap.py --trigger "sistemi başlat"
    python3 scripts/deterministic_bootstrap.py --trigger "neredeyiz"
    python3 scripts/deterministic_bootstrap.py --list
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY_PATH = _REPO_ROOT / "policies" / "policy_intent_runbook_registry.v1.json"
_DEFAULT_WS = ".cache/ws_customer_default"


def _load_registry() -> dict:
    if not _REGISTRY_PATH.exists():
        return {"runbooks": {}}
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def match_runbook(trigger: str, registry: dict) -> tuple[str | None, dict | None]:
    """Find matching runbook by keyword match."""
    trigger_lower = trigger.strip().lower()
    for runbook_id, runbook in registry.get("runbooks", {}).items():
        for t in runbook.get("triggers", []):
            if t.lower() in trigger_lower or trigger_lower in t.lower():
                return runbook_id, runbook
    return None, None


def execute_runbook(runbook_id: str, runbook: dict, *, workspace_root: str, dry_run: bool = False) -> dict:
    """Execute runbook steps in order."""
    steps = runbook.get("steps", [])
    profile = runbook.get("profile", "TASK_EXECUTION")
    results = []

    for i, step_template in enumerate(steps):
        step = step_template.replace("{ws}", workspace_root)
        cmd = f"python3 -m src.ops.manage {step}"

        if dry_run:
            results.append({"step": i, "command": cmd, "status": "DRY_RUN"})
            continue

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=str(_REPO_ROOT)
            )
            status = "OK" if result.returncode == 0 else "FAIL"
            results.append({
                "step": i,
                "command": cmd,
                "status": status,
                "exit_code": result.returncode,
            })
            if result.returncode != 0:
                # Try fallback if available
                fallback = runbook.get("fallback")
                if fallback and i == 0:
                    fb_cmd = f"python3 -m src.ops.manage {fallback.replace('{ws}', workspace_root)}"
                    fb_result = subprocess.run(
                        fb_cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=str(_REPO_ROOT)
                    )
                    results.append({
                        "step": f"{i}_fallback",
                        "command": fb_cmd,
                        "status": "OK" if fb_result.returncode == 0 else "FAIL",
                        "exit_code": fb_result.returncode,
                    })
        except subprocess.TimeoutExpired:
            results.append({"step": i, "command": cmd, "status": "TIMEOUT"})

    all_ok = all(r["status"] in ("OK", "DRY_RUN") for r in results)

    return {
        "status": "OK" if all_ok else "FAIL",
        "runbook_id": runbook_id,
        "profile": profile,
        "workspace_root": workspace_root,
        "steps_total": len(steps),
        "steps_completed": sum(1 for r in results if r["status"] in ("OK", "DRY_RUN")),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic bootstrap runner")
    parser.add_argument("--trigger", help="User intent trigger phrase")
    parser.add_argument("--workspace-root", default=_DEFAULT_WS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", help="List available runbooks")
    args = parser.parse_args()

    registry = _load_registry()

    if args.list:
        for rid, rb in registry.get("runbooks", {}).items():
            triggers = ", ".join(rb.get("triggers", []))
            print(f"  {rid}: [{triggers}] → {len(rb.get('steps', []))} steps ({rb.get('profile', '?')})")
        return 0

    if not args.trigger:
        print(json.dumps({"status": "DECISION_NEEDED", "message": "No trigger provided. Use --list to see available runbooks."}))
        return 1

    runbook_id, runbook = match_runbook(args.trigger, registry)

    if runbook is None:
        print(json.dumps({
            "status": "DECISION_NEEDED",
            "trigger": args.trigger,
            "message": "No matching runbook found. Available triggers:",
            "available": {rid: rb.get("triggers", []) for rid, rb in registry.get("runbooks", {}).items()},
        }))
        return 1

    result = execute_runbook(runbook_id, runbook, workspace_root=args.workspace_root, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
