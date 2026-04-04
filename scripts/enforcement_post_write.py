#!/usr/bin/env python3
"""Enforcement post-write validator — runs required_validations from rule_packet.

Called by Claude Code PostToolUse hook after every Write/Edit.
Reads the last rule_packet.v1.json and executes required_validations.

Hook integration (.claude/settings.json):
    {
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "python3 scripts/enforcement_post_write.py"
      }]
    }
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_WS = _REPO_ROOT / ".cache" / "ws_customer_default"
_PACKET_PATH = _DEFAULT_WS / ".cache" / "reports" / "rule_packet.v1.json"  # legacy path (also written by compiler)

# Validation commands mapped from short names to full commands
_VALIDATION_COMMANDS = {
    "python3 ci/validate_schemas.py": "python3 ci/validate_schemas.py",
    "python3 ci/core_ops_contract_test.py": "python3 ci/core_ops_contract_test.py",
}


def _find_latest_packet() -> Path | None:
    """Find the latest rule packet — try agent-scoped first, then legacy."""
    reports_dir = _DEFAULT_WS / ".cache" / "reports"
    if reports_dir.is_dir():
        # Agent-scoped packets (Phase 1): rule_packet.{agent}.{hash}.v1.json
        scoped = sorted(reports_dir.glob("rule_packet.claude.*.v1.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if scoped:
            return scoped[0]
    # Fallback to legacy path
    if _PACKET_PATH.exists():
        return _PACKET_PATH
    return None


def main() -> int:
    packet_path = _find_latest_packet()
    if not packet_path:
        print(json.dumps({"status": "SKIP", "reason": "no rule_packet found"}))
        return 0

    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(json.dumps({"status": "SKIP", "reason": "rule_packet parse error"}))
        return 0

    validations = packet.get("required_validations", [])
    if not validations:
        print(json.dumps({"status": "SKIP", "reason": "no required_validations"}))
        return 0

    results = []
    for v in validations:
        cmd = _VALIDATION_COMMANDS.get(v, v)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, cwd=str(_REPO_ROOT),
            )
            ok = result.returncode == 0
            results.append({"validation": v, "status": "PASS" if ok else "WARN", "exit_code": result.returncode})
            if not ok:
                # Extract last meaningful line
                last_line = (result.stdout or result.stderr or "").strip().split("\n")[-1][:200]
                results[-1]["detail"] = last_line
        except subprocess.TimeoutExpired:
            results.append({"validation": v, "status": "TIMEOUT"})
        except Exception as e:
            results.append({"validation": v, "status": "ERROR", "detail": str(e)[:100]})

    failed = [r for r in results if r["status"] not in ("PASS",)]
    status = "WARN" if failed else "PASS"

    print(json.dumps({
        "status": status,
        "validations_run": len(results),
        "passed": len(results) - len(failed),
        "warnings": len(failed),
        "results": results,
    }))
    # Post-write is advisory — never block (return 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
