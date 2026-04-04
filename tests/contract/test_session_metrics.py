"""Contract tests for session metrics aggregator (Phase 4).

Validates:
  - Event recording (JSONL append)
  - Compilation tracking (cache hits/misses)
  - Rule usage tracking
  - Scope event tracking
  - Aggregation summary
  - Quality trend detection
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.context_session_metrics import (
    record_metric,
    record_compilation,
    record_rule_usage,
    record_scope_event,
    aggregate_session_metrics,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True)
    return ws


class TestEventRecording:
    def test_record_creates_jsonl(self, workspace: Path) -> None:
        record_metric(workspace, metric_type="test", value=42)
        events_path = workspace / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"
        assert events_path.exists()
        lines = events_path.read_text().strip().split("\n")
        assert len(lines) == 1
        ev = json.loads(lines[0])
        assert ev["type"] == "test"
        assert ev["value"] == 42

    def test_record_appends(self, workspace: Path) -> None:
        record_metric(workspace, metric_type="a", value=1)
        record_metric(workspace, metric_type="b", value=2)
        events_path = workspace / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"
        lines = events_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_record_compilation(self, workspace: Path) -> None:
        record_compilation(workspace, cache_hit=True, rules_loaded=15, domain="frontend")
        events_path = workspace / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"
        ev = json.loads(events_path.read_text().strip())
        assert ev["type"] == "compilation"
        assert ev["meta"]["cache_hit"] is True
        assert ev["meta"]["rules_loaded"] == 15

    def test_record_rule_usage(self, workspace: Path) -> None:
        record_rule_usage(workspace, rule_id="R-001", action="applied")
        events_path = workspace / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"
        ev = json.loads(events_path.read_text().strip())
        assert ev["type"] == "rule_usage"
        assert ev["value"] == "applied"

    def test_record_scope_event(self, workspace: Path) -> None:
        record_scope_event(workspace, event_type="warn", files_count=12)
        events_path = workspace / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"
        ev = json.loads(events_path.read_text().strip())
        assert ev["type"] == "scope_event"
        assert ev["value"] == "warn"


class TestAggregation:
    def test_empty_events(self, workspace: Path) -> None:
        summary = aggregate_session_metrics(workspace)
        assert summary["version"] == "v1"
        assert summary["total_writes"] == 0
        assert summary["quality_trend"] == "STABLE"

    def test_aggregates_compilations(self, workspace: Path) -> None:
        record_compilation(workspace, cache_hit=True, rules_loaded=10, domain="frontend")
        record_compilation(workspace, cache_hit=False, rules_loaded=8, domain="backend")
        record_compilation(workspace, cache_hit=True, rules_loaded=10, domain="frontend")
        summary = aggregate_session_metrics(workspace)
        assert summary["total_writes"] == 3
        assert summary["cache_hits"] == 2
        assert summary["cache_misses"] == 1
        assert summary["cache_hit_rate"] == round(2 / 3, 4)
        assert summary["domain_switches"] == 2

    def test_aggregates_rule_usage(self, workspace: Path) -> None:
        record_rule_usage(workspace, rule_id="R-001", action="applied")
        record_rule_usage(workspace, rule_id="R-002", action="violated")
        record_rule_usage(workspace, rule_id="R-003", action="ignored")
        summary = aggregate_session_metrics(workspace)
        assert summary["rules_applied"] == 1
        assert summary["rules_violated"] == 1
        assert summary["rules_ignored"] == 1

    def test_quality_trend_improving(self, workspace: Path) -> None:
        record_compilation(workspace, cache_hit=True, rules_loaded=5, domain="backend")
        record_compilation(workspace, cache_hit=True, rules_loaded=5, domain="backend")
        record_rule_usage(workspace, rule_id="R-001", action="applied")
        summary = aggregate_session_metrics(workspace)
        assert summary["quality_trend"] == "IMPROVING"

    def test_quality_trend_degrading(self, workspace: Path) -> None:
        record_compilation(workspace, cache_hit=False, rules_loaded=5, domain="backend")
        record_compilation(workspace, cache_hit=False, rules_loaded=5, domain="backend")
        record_compilation(workspace, cache_hit=False, rules_loaded=5, domain="backend")
        record_compilation(workspace, cache_hit=False, rules_loaded=5, domain="backend")
        record_rule_usage(workspace, rule_id="R-001", action="violated")
        record_rule_usage(workspace, rule_id="R-002", action="violated")
        summary = aggregate_session_metrics(workspace)
        assert summary["quality_trend"] == "DEGRADING"

    def test_writes_summary_json(self, workspace: Path) -> None:
        record_compilation(workspace, cache_hit=True, rules_loaded=5, domain="frontend")
        aggregate_session_metrics(workspace)
        summary_path = workspace / ".cache" / "reports" / "context_session_metrics.v1.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["version"] == "v1"

    def test_scope_events_counted(self, workspace: Path) -> None:
        record_scope_event(workspace, event_type="warn", files_count=5)
        record_scope_event(workspace, event_type="block", files_count=10)
        summary = aggregate_session_metrics(workspace)
        assert summary["scope_warnings"] == 1
        assert summary["scope_blocks"] == 1
