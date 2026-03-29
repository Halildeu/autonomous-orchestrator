#!/usr/bin/env python3
"""Golden task eval runner — validates enforcement pipeline against known tasks.

Reads golden task definitions from fixtures/golden_tasks/, runs
enforcement_pre_write.py for each, and compares results to expectations.

Usage:
    python3 ci/eval_enforcement_golden_tasks.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TASKS_DIR = _REPO_ROOT / "fixtures" / "golden_tasks"
_SCRIPT = _REPO_ROOT / "scripts" / "enforcement_pre_write.py"


def _run_enforcement(target_path: str) -> dict:
    """Run enforcement_pre_write.py and return parsed output."""
    # Ensure CORE_UNLOCK is not set (test BLOCKED scenarios)
    env = {k: v for k, v in os.environ.items() if k != "CORE_UNLOCK"}
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--target-path", target_path],
        capture_output=True, text=True, timeout=30, env=env,
    )
    try:
        return {**json.loads(result.stdout), "_rc": result.returncode}
    except json.JSONDecodeError:
        return {"_rc": result.returncode, "status": "ERROR", "_stdout": result.stdout[:200]}


def main() -> int:
    if not _TASKS_DIR.exists():
        print(json.dumps({"status": "SKIP", "reason": "No golden tasks directory"}))
        return 0

    tasks = sorted(_TASKS_DIR.glob("task_*.v1.json"))
    if not tasks:
        print(json.dumps({"status": "SKIP", "reason": "No golden tasks found"}))
        return 0

    passed = 0
    failed = 0
    results = []

    for task_path in tasks:
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task_id = task.get("task_id", task_path.stem)
        target_path = task.get("target_path", "")
        expected_auth = task.get("expected_authorize", "PASS")

        out = _run_enforcement(target_path)
        actual_status = out.get("status", "ERROR")

        ok = actual_status == expected_auth
        if ok:
            passed += 1
            results.append({"task_id": task_id, "result": "PASS", "expected": expected_auth, "actual": actual_status})
        else:
            failed += 1
            results.append({
                "task_id": task_id, "result": "FAIL",
                "expected": expected_auth, "actual": actual_status,
                "detail": out.get("reasons", out.get("_stdout", "")),
            })
            print(f"FAIL [{task_id}]: expected={expected_auth} actual={actual_status}", file=sys.stderr)

    summary = {
        "status": "OK" if failed == 0 else "FAIL",
        "tasks_total": len(tasks),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
