"""Contract tests for Codex enforcement bridge compiler integration (R1).

Validates that codex_enforcement_bridge uses the unified context compiler
instead of directly calling compile_rules_digest + write_authorize.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    return ws


class TestCodexBridgeUsesCompiler:
    def test_preflight_calls_compiler(self, workspace: Path) -> None:
        """Codex bridge must use context_compiler, not direct digest+auth."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.ops.context_compiler import clear_cache
        clear_cache()
        from scripts.codex_enforcement_bridge import _compile_preflight

        result = _compile_preflight(["schemas/test.schema.v1.json"], workspace)
        assert result["status"] in ("PASS", "BLOCKED", "WARN")
        assert result["paths_checked"] == 1
        assert len(result["results"]) == 1

        r = result["results"][0]
        assert "target_path" in r
        assert "authorization" in r
        assert "layer" in r
        assert "domain" in r

    def test_preflight_blocked_for_src(self, workspace: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.ops.context_compiler import clear_cache
        clear_cache()
        from scripts.codex_enforcement_bridge import _compile_preflight

        result = _compile_preflight(["src/ops/foo.py"], workspace)
        # src/ requires CORE_UNLOCK — should be BLOCKED
        blocked = result.get("blocked", [])
        assert len(blocked) >= 1

    def test_preflight_produces_agent_scoped_artifact(self, workspace: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.ops.context_compiler import clear_cache
        clear_cache()
        from scripts.codex_enforcement_bridge import _compile_preflight

        _compile_preflight(["schemas/test.schema.v1.json"], workspace)

        # Should have created a codex-scoped artifact
        reports = workspace / ".cache" / "reports"
        codex_files = list(reports.glob("rule_packet.codex.*.v1.json"))
        assert len(codex_files) >= 1

    def test_claude_and_codex_artifacts_separate(self, workspace: Path) -> None:
        """Verify no race condition — different agents get different files."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from scripts.codex_enforcement_bridge import _compile_preflight
        from src.ops.context_compiler import compile_enforcement_context, clear_cache

        clear_cache()
        # Claude compile
        compile_enforcement_context(
            workspace_root=workspace,
            target_path="schemas/test.schema.v1.json",
            agent_id="claude",
        )
        clear_cache()
        # Codex compile
        _compile_preflight(["schemas/test.schema.v1.json"], workspace)

        reports = workspace / ".cache" / "reports"
        claude_files = list(reports.glob("rule_packet.claude.*.v1.json"))
        codex_files = list(reports.glob("rule_packet.codex.*.v1.json"))
        assert len(claude_files) >= 1
        assert len(codex_files) >= 1

        # Filenames must differ
        claude_names = {f.name for f in claude_files}
        codex_names = {f.name for f in codex_files}
        assert claude_names.isdisjoint(codex_names)
