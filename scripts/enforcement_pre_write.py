#!/usr/bin/env python3
"""Enforcement pre-write pipeline — unified gate for Write/Edit operations.

Called by Claude Code PreToolUse hook before every Write/Edit.
Reads file_path from stdin JSON (hook input), compiles rule packet,
checks write authorization, and exits 0 (PASS) or 1 (BLOCKED).

Also callable standalone:
    python3 scripts/enforcement_pre_write.py --target-path src/ops/foo.py

Hook integration (.claude/settings.json):
    {
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "python3 scripts/enforcement_pre_write.py"
      }]
    }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_WS = _REPO_ROOT / ".cache" / "ws_customer_default"

sys.path.insert(0, str(_REPO_ROOT))


def _read_target_from_stdin() -> str | None:
    """Read target file path from Claude Code hook stdin JSON."""
    if sys.stdin.isatty():
        return None
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input", {})
        return tool_input.get("file_path")
    except (json.JSONDecodeError, AttributeError):
        return None


def _to_repo_relative(abs_path: str) -> str:
    """Convert absolute path to repo-relative."""
    try:
        return str(Path(abs_path).resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return abs_path


def compile_rule_packet(target_path: str, workspace_root: Path) -> dict:
    """Compile a rule packet via unified context compiler.

    Delegates to src.ops.context_compiler.compile_enforcement_context()
    which is the single assembly layer for all agents (Claude + Codex).
    """
    from src.ops.context_compiler import compile_enforcement_context

    result = compile_enforcement_context(
        workspace_root=workspace_root,
        target_path=target_path,
        agent_id="claude",
    )

    # Return legacy-compatible packet structure
    return {
        "version": result["version"],
        "generated_at": result["compiled_at"],
        "target_path": result["target_path"],
        "profile_id": result["profile"]["id"],
        "authorization": result["authorization"],
        "rules": result["rules"],
        "required_validations": result["required_validations"],
        "evidence_required": result["evidence_required"],
    }


def main() -> int:
    # Determine target path: CLI arg or stdin JSON
    target_path = None

    # CLI arg
    if "--target-path" in sys.argv:
        idx = sys.argv.index("--target-path")
        if idx + 1 < len(sys.argv):
            target_path = sys.argv[idx + 1]

    # Stdin (hook mode)
    if target_path is None:
        abs_path = _read_target_from_stdin()
        if abs_path:
            target_path = _to_repo_relative(abs_path)

    if not target_path:
        # No target path — skip silently (non-blocking)
        print(json.dumps({"status": "SKIP", "reason": "no target path"}))
        return 0

    target_path = _to_repo_relative(target_path)

    # Workspace root
    ws = _DEFAULT_WS
    if "--workspace-root" in sys.argv:
        idx = sys.argv.index("--workspace-root")
        if idx + 1 < len(sys.argv):
            ws = Path(sys.argv[idx + 1])

    packet = compile_rule_packet(target_path, ws)
    status = packet["authorization"]["status"]

    if status == "BLOCKED":
        reasons = packet["authorization"].get("deny_reasons", [])
        print(json.dumps({
            "status": "BLOCKED",
            "target_path": target_path,
            "reasons": reasons,
            "message": f"Write blocked: {'; '.join(reasons)}",
        }))
        return 1

    # PASS or WARN — print summary for agent context
    rules = packet.get("rules", {})
    summary_lines = [
        f"layer={rules.get('layer', '?')}",
        f"domain={rules.get('domain', '?')}",
        f"profile={packet.get('profile_id', '?')}",
    ]
    domain_rules = rules.get("domain_rules", [])
    if domain_rules:
        summary_lines.append(f"rules={len(domain_rules)} domain-specific")

    print(json.dumps({
        "status": status,
        "target_path": target_path,
        "summary": " | ".join(summary_lines),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
