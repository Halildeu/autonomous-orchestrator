"""Contract tests for rule effectiveness tracker (Phase 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.rule_effectiveness import (
    track_rule_usage, compute_effectiveness, classify_tier,
    get_rules_by_tier, increment_session_count,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    return ws


class TestTracking:
    def test_track_loaded(self, workspace: Path) -> None:
        track_rule_usage(workspace, rule_id="R-001", action="loaded")
        results = compute_effectiveness(workspace)
        assert len(results) == 1
        assert results[0]["rule_id"] == "R-001"
        assert results[0]["total_loads"] == 1

    def test_track_multiple_actions(self, workspace: Path) -> None:
        track_rule_usage(workspace, rule_id="R-001", action="loaded")
        track_rule_usage(workspace, rule_id="R-001", action="loaded")
        track_rule_usage(workspace, rule_id="R-001", action="applied")
        results = compute_effectiveness(workspace)
        r = results[0]
        assert r["total_loads"] == 2
        assert r["times_applied"] == 1


class TestEffectivenessScoring:
    def test_high_effectiveness(self, workspace: Path) -> None:
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-001", action="loaded")
        for _ in range(8):
            track_rule_usage(workspace, rule_id="R-001", action="applied")
        results = compute_effectiveness(workspace)
        assert results[0]["effectiveness_score"] == 0.8

    def test_zero_effectiveness(self, workspace: Path) -> None:
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-001", action="loaded")
        results = compute_effectiveness(workspace)
        assert results[0]["effectiveness_score"] == 0.0

    def test_violation_counts_as_relevant(self, workspace: Path) -> None:
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-001", action="loaded")
        for _ in range(5):
            track_rule_usage(workspace, rule_id="R-001", action="violated")
        results = compute_effectiveness(workspace)
        assert results[0]["effectiveness_score"] == 0.5


class TestTierClassification:
    def test_hot(self) -> None:
        assert classify_tier(0.8, 10, 5) == "HOT"

    def test_warm(self) -> None:
        assert classify_tier(0.5, 10, 5) == "WARM"

    def test_cold(self) -> None:
        assert classify_tier(0.1, 10, 5) == "COLD"

    def test_dead(self) -> None:
        assert classify_tier(0.0, 0, 30) == "DEAD"

    def test_not_dead_if_sessions_low(self) -> None:
        assert classify_tier(0.0, 0, 5) == "COLD"


class TestTierGrouping:
    def test_group_by_tier(self, workspace: Path) -> None:
        # HOT rule
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-HOT", action="loaded")
            track_rule_usage(workspace, rule_id="R-HOT", action="applied")
        # COLD rule
        for _ in range(10):
            track_rule_usage(workspace, rule_id="R-COLD", action="loaded")

        tiers = get_rules_by_tier(workspace)
        assert "R-HOT" in tiers["HOT"]
        assert "R-COLD" in tiers["COLD"]


class TestSessionCount:
    def test_increment(self, workspace: Path) -> None:
        c1 = increment_session_count(workspace)
        c2 = increment_session_count(workspace)
        assert c1 == 1
        assert c2 == 2
