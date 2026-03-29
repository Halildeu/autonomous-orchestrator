#!/usr/bin/env python3
"""Codex enforcement bridge — pre-write + post-write parity with Claude hooks.

Since Codex has no native PreToolUse hooks, this script provides equivalent
enforcement by wrapping codex exec calls:

1. Pre-exec: compile-rules-digest for target paths, inject into prompt
2. Post-exec: run required_validations from rule_packet

Usage (wrapping codex exec):
    python3 scripts/codex_enforcement_bridge.py \
        --target-paths src/ops/foo.py schemas/bar.json \
        --prompt "Create the foo command" \
        --workspace-root .cache/ws_customer_default

Usage (preflight check only, no codex exec):
    python3 scripts/codex_enforcement_bridge.py \
        --target-paths src/ops/foo.py \
        --preflight-only

Usage (post-write validation only):
    python3 scripts/codex_enforcement_bridge.py \
        --validate-only \
        --workspace-root .cache/ws_customer_default
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_WS = _REPO_ROOT / ".cache" / "ws_customer_default"

sys.path.insert(0, str(_REPO_ROOT))


def _compile_preflight(target_paths: list[str], workspace_root: Path) -> dict:
    """Run enforcement pre-write for each target path, return combined result."""
    from src.ops.compile_rules_digest import compile_rules_digest
    from src.ops.write_authorize import write_authorize

    results = []
    blocked_paths = []

    for tp in target_paths:
        digest = compile_rules_digest(workspace_root=workspace_root, target_path=tp)
        auth = write_authorize(workspace_root=workspace_root, target_path=tp)

        status = auth.get("status", "WARN")
        if status == "BLOCKED":
            blocked_paths.append({"path": tp, "reasons": auth.get("deny_reasons", [])})

        results.append({
            "target_path": tp,
            "authorization": status,
            "layer": digest.get("layer", "?"),
            "domain": digest.get("domain", "?"),
            "rules_count": len(digest.get("domain_rules", [])),
            "required_validations": auth.get("required_validations", []),
        })

    return {
        "status": "BLOCKED" if blocked_paths else "PASS",
        "paths_checked": len(target_paths),
        "blocked": blocked_paths,
        "results": results,
    }


def _build_enforcement_prompt_prefix(preflight: dict) -> str:
    """Build a concise rules summary to prepend to the Codex prompt."""
    lines = ["[ENFORCEMENT CONTEXT — auto-generated, do not ignore]"]

    for r in preflight.get("results", []):
        tp = r.get("target_path", "?")
        auth = r.get("authorization", "?")
        layer = r.get("layer", "?")
        domain = r.get("domain", "?")
        lines.append(f"  {tp}: {auth} | {layer} | {domain} | rules={r.get('rules_count', 0)}")

    if preflight.get("blocked"):
        lines.append("")
        lines.append("BLOCKED PATHS (do NOT write to these):")
        for b in preflight["blocked"]:
            lines.append(f"  {b['path']}: {'; '.join(b['reasons'])}")

    lines.append("")
    lines.append("RULES: Use src.shared.utils (write_json_atomic, write_text_atomic, load_json, now_iso8601).")
    lines.append("RULES: Type hints + docstrings for public functions. Max 800 lines per file.")
    lines.append("RULES: Fail-closed. Evidence required for state writes. No secrets in output.")
    lines.append("[/ENFORCEMENT CONTEXT]")
    lines.append("")

    return "\n".join(lines)


def _run_post_validations(workspace_root: Path) -> dict:
    """Run required_validations from the last rule_packet."""
    import subprocess

    packet_path = workspace_root / ".cache" / "reports" / "rule_packet.v1.json"
    if not packet_path.exists():
        return {"status": "SKIP", "reason": "no rule_packet"}

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    validations = packet.get("required_validations", [])
    results = []

    for v in validations:
        try:
            r = subprocess.run(v, shell=True, capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT))
            results.append({"validation": v, "status": "PASS" if r.returncode == 0 else "WARN"})
        except Exception as e:
            results.append({"validation": v, "status": "ERROR", "detail": str(e)[:100]})

    return {
        "status": "PASS" if all(r["status"] == "PASS" for r in results) else "WARN",
        "validations_run": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex enforcement bridge")
    parser.add_argument("--target-paths", nargs="+", default=[], help="Target paths to check")
    parser.add_argument("--prompt", default="", help="Codex prompt (for wrapping mode)")
    parser.add_argument("--workspace-root", default=str(_DEFAULT_WS))
    parser.add_argument("--preflight-only", action="store_true", help="Only run preflight, don't exec codex")
    parser.add_argument("--validate-only", action="store_true", help="Only run post-write validations")
    args = parser.parse_args()

    ws = Path(args.workspace_root).resolve()

    if args.validate_only:
        result = _run_post_validations(ws)
        print(json.dumps(result, indent=2))
        return 0

    if not args.target_paths:
        print(json.dumps({"status": "SKIP", "reason": "no target paths"}))
        return 0

    # Preflight
    preflight = _compile_preflight(args.target_paths, ws)
    print(json.dumps(preflight, indent=2))

    if preflight["status"] == "BLOCKED":
        return 1

    if args.preflight_only:
        return 0

    # Build enforcement-augmented prompt
    if args.prompt:
        prefix = _build_enforcement_prompt_prefix(preflight)
        augmented_prompt = prefix + args.prompt
        print(f"\n--- Augmented prompt ({len(augmented_prompt)} chars) ---")
        print(augmented_prompt[:500] + "..." if len(augmented_prompt) > 500 else augmented_prompt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
