"""Contract tests for ACE context evolution engine (Phase 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.rule_effectiveness import track_rule_usage, increment_session_count
from src.ops.fact_evolution import run_evolution_cycle


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    return ws


class TestEvolutionCycle:
    def test_skip_when_no_data(self, workspace: Path) -> None:
        result = run_evolution_cycle(workspace)
        assert result["status"] == "OK"
        assert result["proposals_count"] == 0

    def test_generates_prune_for_dead_rules(self, workspace: Path) -> None:
        # Create a DEAD rule: 0 loads, 30+ sessions
        track_rule_usage(workspace, rule_id="R-DEAD", action="loaded")
        # Reset loads to 0 by directly manipulating — simulate DEAD
        from src.ops.rule_effectiveness import _load_state, _save_state
        state = _load_state(workspace)
        state["rules"]["R-DEAD"]["total_loads"] = 0
        state["session_count"] = 35
        _save_state(workspace, state)

        result = run_evolution_cycle(workspace)
        prune_proposals = [p for p in result["proposals"] if p["type"] == "prune"]
        assert len(prune_proposals) >= 1
        assert prune_proposals[0]["confidence"] >= 0.9

    def test_auto_applies_high_confidence(self, workspace: Path) -> None:
        # Setup DEAD rule (auto-apply threshold = 0.9, DEAD prune confidence = 0.95)
        track_rule_usage(workspace, rule_id="R-DEAD2", action="loaded")
        from src.ops.rule_effectiveness import _load_state, _save_state
        state = _load_state(workspace)
        state["rules"]["R-DEAD2"]["total_loads"] = 0
        state["session_count"] = 35
        _save_state(workspace, state)

        result = run_evolution_cycle(workspace)
        auto = [p for p in result["proposals"] if p.get("auto_applied")]
        assert len(auto) >= 1

    def test_demote_low_effectiveness_rule(self, workspace: Path) -> None:
        # COLD rule with many loads, low score
        for _ in range(15):
            track_rule_usage(workspace, rule_id="R-LOW", action="loaded")
        result = run_evolution_cycle(workspace)
        demote_proposals = [p for p in result["proposals"] if p["type"] == "demote"]
        assert len(demote_proposals) >= 1

    def test_promote_high_effectiveness_rule(self, workspace: Path) -> None:
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-HIGH", action="loaded")
            track_rule_usage(workspace, rule_id="R-HIGH", action="applied")
        result = run_evolution_cycle(workspace)
        promote_proposals = [p for p in result["proposals"] if p["type"] == "promote"]
        assert len(promote_proposals) >= 1

    def test_writes_proposals_file(self, workspace: Path) -> None:
        run_evolution_cycle(workspace)
        proposals_path = workspace / ".cache" / "reports" / "context_evolution_proposals.v1.json"
        assert proposals_path.exists()

    def test_tier_summary_in_result(self, workspace: Path) -> None:
        track_rule_usage(workspace, rule_id="R-A", action="loaded")
        result = run_evolution_cycle(workspace)
        assert "tier_summary" in result
