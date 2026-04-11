"""Contract test for parallel agent race condition fix (R2).

Validates that concurrent compilations from different agents produce
separate artifact files without corruption.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("src.ops.context_compiler", reason="context_compiler not yet implemented")

from src.ops.context_compiler import compile_enforcement_context, clear_cache


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_cache()


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    (ws / ".cache" / "index").mkdir(parents=True)
    return ws


class TestParallelRaceCondition:
    def test_concurrent_agents_no_corruption(self, workspace: Path) -> None:
        """Two agents compiling simultaneously must not corrupt each other's artifact."""

        def compile_claude():
            clear_cache()
            return compile_enforcement_context(
                workspace_root=workspace,
                target_path="schemas/test.schema.v1.json",
                agent_id="claude",
            )

        def compile_codex():
            clear_cache()
            return compile_enforcement_context(
                workspace_root=workspace,
                target_path="schemas/test.schema.v1.json",
                agent_id="codex",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_claude = pool.submit(compile_claude)
            f_codex = pool.submit(compile_codex)
            result_claude = f_claude.result()
            result_codex = f_codex.result()

        # Both should succeed
        assert result_claude["agent_id"] == "claude"
        assert result_codex["agent_id"] == "codex"

        # Both artifacts should exist and be valid JSON
        reports = workspace / ".cache" / "reports"
        claude_files = list(reports.glob("rule_packet.claude.*.v1.json"))
        codex_files = list(reports.glob("rule_packet.codex.*.v1.json"))

        assert len(claude_files) >= 1
        assert len(codex_files) >= 1

        # Validate JSON integrity
        for f in claude_files + codex_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert data["version"] == "v1"
            assert "authorization" in data

    def test_same_agent_concurrent_different_targets(self, workspace: Path) -> None:
        """Same agent, different targets, concurrent — unique artifacts."""

        def compile_schema():
            clear_cache()
            return compile_enforcement_context(
                workspace_root=workspace,
                target_path="schemas/test.schema.v1.json",
                agent_id="claude",
                request_hash="schema01",
            )

        def compile_policy():
            clear_cache()
            return compile_enforcement_context(
                workspace_root=workspace,
                target_path="policies/test.v1.json",
                agent_id="claude",
                request_hash="policy01",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(compile_schema)
            f2 = pool.submit(compile_policy)
            r1 = f1.result()
            r2 = f2.result()

        # Different targets → different fingerprints
        assert r1["target_path"] != r2["target_path"]

        # Both artifacts valid
        reports = workspace / ".cache" / "reports"
        all_packets = list(reports.glob("rule_packet.claude.*.v1.json"))
        assert len(all_packets) >= 2

        for f in all_packets:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert data["version"] == "v1"
