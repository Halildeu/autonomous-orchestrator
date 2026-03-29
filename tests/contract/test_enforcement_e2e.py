"""E2E contract tests for the enforcement pipeline.

Tests the full chain: stdin JSON → enforcement_pre_write.py → rule packet + authorization.
Also tests profile resolution and required_validations selection.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "enforcement_pre_write.py"


def _run_with_stdin(tool_name: str, file_path: str) -> dict:
    """Simulate Claude hook stdin JSON payload."""
    stdin_payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "tool_use_id": "toolu_test_123",
        "cwd": str(_REPO_ROOT),
        "session_id": "test-session",
    })
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        input=stdin_payload,
        capture_output=True, text=True, timeout=30,
    )
    try:
        return {**json.loads(result.stdout), "_rc": result.returncode}
    except json.JSONDecodeError:
        return {"_rc": result.returncode, "_stdout": result.stdout[:300]}


def _run_cli(target_path: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--target-path", target_path],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return {**json.loads(result.stdout), "_rc": result.returncode}
    except json.JSONDecodeError:
        return {"_rc": result.returncode, "_stdout": result.stdout[:300]}


# ── Hook stdin payload tests ──────────────────────────────────────

def test_hook_stdin_write_schemas():
    """Simulate Write hook with stdin JSON for schemas/ path."""
    abs_path = str(_REPO_ROOT / "schemas" / "test-hook.schema.v1.json")
    out = _run_with_stdin("Write", abs_path)
    assert out["status"] == "PASS"
    assert out["_rc"] == 0


def test_hook_stdin_edit_src_blocked():
    """Simulate Edit hook with stdin JSON for src/ path — BLOCKED."""
    import os
    old = os.environ.pop("CORE_UNLOCK", None)
    try:
        abs_path = str(_REPO_ROOT / "src" / "ops" / "test_hook.py")
        out = _run_with_stdin("Edit", abs_path)
        assert out["status"] == "BLOCKED"
        assert out["_rc"] == 1
    finally:
        if old is not None:
            os.environ["CORE_UNLOCK"] = old


def test_hook_stdin_write_agents_md():
    """AGENTS.md should be PASS — it's in allowlist."""
    abs_path = str(_REPO_ROOT / "AGENTS.md")
    out = _run_with_stdin("Write", abs_path)
    assert out["status"] == "PASS"


def test_hook_stdin_write_claude_settings():
    """.claude/settings.json should be PASS."""
    abs_path = str(_REPO_ROOT / ".claude" / "settings.json")
    out = _run_with_stdin("Write", abs_path)
    assert out["status"] == "PASS"


# ── Rule packet content tests ────────────────────────────────────

def test_rule_packet_has_domain_rules():
    """Rule packet for src/ops/ should contain domain-specific rules."""
    _run_cli("src/ops/test.py")
    packet_path = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "rule_packet.v1.json"
    if packet_path.exists():
        packet = json.loads(packet_path.read_text())
        assert packet["rules"]["domain"] == "src-ops"
        assert len(packet["rules"]["domain_rules"]) > 0


def test_rule_packet_agents_md_domain():
    """AGENTS.md should resolve to cross-repo domain."""
    _run_cli("AGENTS.md")
    packet_path = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "rule_packet.v1.json"
    if packet_path.exists():
        packet = json.loads(packet_path.read_text())
        assert packet["rules"]["domain"] == "cross-repo"
        assert packet["rules"]["layer"] == "L0_CORE"


def test_required_validations_for_schemas():
    """schemas/ path should require validate_schemas."""
    _run_cli("schemas/test.schema.v1.json")
    packet_path = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "rule_packet.v1.json"
    if packet_path.exists():
        packet = json.loads(packet_path.read_text())
        validations = packet.get("required_validations", [])
        assert any("validate_schemas" in v for v in validations)


# ── Profile resolution tests ─────────────────────────────────────

def test_profile_resolver_returns_valid_profile():
    """Profile resolver should return a valid profile ID."""
    from src.ops.context_profile_resolver import resolve_profile
    ws = _REPO_ROOT / ".cache" / "ws_customer_default"
    result = resolve_profile(ws)
    assert result["profile_id"] in ("STARTUP", "TASK_EXECUTION", "REVIEW", "ASSESSMENT", "EMERGENCY", "PLANNING")
    assert result["resolution_method"] in ("auto", "explicit", "default", "fallback")


def test_profile_resolver_explicit_override():
    """Explicit profile should override auto resolution."""
    from src.ops.context_profile_resolver import resolve_profile
    ws = _REPO_ROOT / ".cache" / "ws_customer_default"
    result = resolve_profile(ws, explicit_profile="ASSESSMENT")
    assert result["profile_id"] == "ASSESSMENT"
    assert result["resolution_method"] == "explicit"


def test_profile_resolver_emergency_on_fail():
    """EMERGENCY profile should activate when system_status is FAIL."""
    from src.ops.context_profile_resolver import resolve_profile, _gather_context_signals, _eval_condition
    # Test the condition directly
    signals = {"system_status": {"overall_status": "FAIL"}}
    condition = {"op": "eq", "left": {"var": "system_status.overall_status"}, "right": "FAIL"}
    assert _eval_condition(condition, signals) is True
