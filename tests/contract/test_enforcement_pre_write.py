"""Contract tests for the enforcement pre-write pipeline."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "enforcement_pre_write.py"


def _run(target_path: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--target-path", target_path],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return {**json.loads(result.stdout), "_rc": result.returncode}
    except json.JSONDecodeError:
        return {"_rc": result.returncode, "_stdout": result.stdout, "_stderr": result.stderr}


def test_schemas_pass():
    """Schema path should PASS — in allowlist, no CORE_UNLOCK needed."""
    out = _run("schemas/test.schema.v1.json")
    assert out["status"] == "PASS"
    assert out["_rc"] == 0


def test_policies_pass():
    """Policy path should PASS."""
    out = _run("policies/policy_test.v1.json")
    assert out["status"] == "PASS"
    assert out["_rc"] == 0


def test_cache_pass():
    """Workspace cache path should PASS."""
    out = _run(".cache/ws_customer_default/.cache/reports/test.json")
    assert out["status"] == "PASS"
    assert out["_rc"] == 0


def test_src_blocked_without_core_unlock():
    """src/ path should be BLOCKED without CORE_UNLOCK=1."""
    import os
    old = os.environ.pop("CORE_UNLOCK", None)
    try:
        out = _run("src/ops/new_command.py")
        assert out["status"] == "BLOCKED"
        assert out["_rc"] == 1
        assert any("CORE_UNLOCK" in r for r in out.get("reasons", []))
    finally:
        if old is not None:
            os.environ["CORE_UNLOCK"] = old


def test_rule_packet_written():
    """Rule packet artifact should be written to workspace."""
    _run("schemas/test.schema.v1.json")
    packet_path = _REPO_ROOT / ".cache" / "ws_customer_default" / ".cache" / "reports" / "rule_packet.v1.json"
    assert packet_path.exists()
    packet = json.loads(packet_path.read_text())
    assert packet["version"] == "v1"
    assert "authorization" in packet
    assert "rules" in packet
