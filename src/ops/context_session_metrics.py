"""Context session metrics — track rule usage, cache performance, and quality.

Append-only JSONL for individual events, JSON summary for session aggregation.
Health scorer reads the summary for component 7-9 scoring.

State:
  - Events: .cache/reports/context_session_metrics_events.v1.jsonl (append-only)
  - Summary: .cache/reports/context_session_metrics.v1.json (rebuilt on aggregate)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.shared.utils import load_json_or_default, now_iso8601, write_json_atomic

logger = logging.getLogger(__name__)


def _events_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "context_session_metrics_events.v1.jsonl"


def _summary_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "context_session_metrics.v1.json"


# ── Event Recording ─────────────────────────────────────────────


def record_metric(
    workspace_root: Path,
    *,
    metric_type: str,
    value: Any = 1,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a single metric event (append-only JSONL)."""
    path = _events_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": now_iso8601(),
        "type": metric_type,
        "value": value,
    }
    if metadata:
        event["meta"] = metadata

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to record metric: %s", exc)


def record_compilation(
    workspace_root: Path,
    *,
    cache_hit: bool,
    rules_loaded: int,
    compilation_ms: int = 0,
    domain: str = "general",
) -> None:
    """Record a compilation event (convenience wrapper)."""
    record_metric(
        workspace_root,
        metric_type="compilation",
        metadata={
            "cache_hit": cache_hit,
            "rules_loaded": rules_loaded,
            "compilation_ms": compilation_ms,
            "domain": domain,
        },
    )


def record_rule_usage(
    workspace_root: Path,
    *,
    rule_id: str,
    action: str,  # "applied", "violated", "ignored"
) -> None:
    """Record a rule usage event."""
    record_metric(
        workspace_root,
        metric_type="rule_usage",
        value=action,
        metadata={"rule_id": rule_id},
    )


def record_scope_event(
    workspace_root: Path,
    *,
    event_type: str,  # "warn", "block", "expand"
    files_count: int = 0,
) -> None:
    """Record a scope guard event."""
    record_metric(
        workspace_root,
        metric_type="scope_event",
        value=event_type,
        metadata={"files_count": files_count},
    )


# ── Aggregation ─────────────────────────────────────────────────


def aggregate_session_metrics(workspace_root: Path) -> dict[str, Any]:
    """Aggregate all events into a session summary.

    Reads JSONL events, computes totals, writes summary JSON.
    Returns the summary dict.
    """
    events = _load_events(workspace_root)

    # Counters
    total_writes = 0
    rules_loaded = 0
    rules_applied = 0
    rules_violated = 0
    rules_ignored = 0
    cache_hits = 0
    cache_misses = 0
    scope_warnings = 0
    scope_blocks = 0
    domain_switches: set[str] = set()
    compilation_times: list[int] = []

    for ev in events:
        ev_type = ev.get("type", "")
        meta = ev.get("meta", {})

        if ev_type == "compilation":
            total_writes += 1
            if meta.get("cache_hit"):
                cache_hits += 1
            else:
                cache_misses += 1
            rules_loaded += meta.get("rules_loaded", 0)
            domain_switches.add(meta.get("domain", "general"))
            ms = meta.get("compilation_ms", 0)
            if ms > 0:
                compilation_times.append(ms)

        elif ev_type == "rule_usage":
            action = ev.get("value", "")
            if action == "applied":
                rules_applied += 1
            elif action == "violated":
                rules_violated += 1
            elif action == "ignored":
                rules_ignored += 1

        elif ev_type == "scope_event":
            val = ev.get("value", "")
            if val == "warn":
                scope_warnings += 1
            elif val == "block":
                scope_blocks += 1

    total_cache = cache_hits + cache_misses
    cache_hit_rate = round(cache_hits / total_cache, 4) if total_cache > 0 else 0.0
    avg_compilation_ms = int(sum(compilation_times) / len(compilation_times)) if compilation_times else 0

    # Determine quality trend (only assess when enough data exists)
    rules_never_used = max(0, rules_loaded - rules_applied - rules_violated)
    quality_trend = "STABLE"
    if total_writes > 0:
        if rules_applied > 0 and rules_violated == 0 and cache_hit_rate >= 0.5:
            quality_trend = "IMPROVING"
        elif rules_violated > rules_applied or (total_cache > 2 and cache_hit_rate < 0.3):
            quality_trend = "DEGRADING"

    summary = {
        "version": "v1",
        "generated_at": now_iso8601(),
        "total_writes": total_writes,
        "rules_loaded": rules_loaded,
        "rules_applied": rules_applied,
        "rules_violated": rules_violated,
        "rules_ignored": rules_ignored,
        "rules_never_used": rules_never_used,
        "scope_warnings": scope_warnings,
        "scope_blocks": scope_blocks,
        "domain_switches": len(domain_switches),
        "domains_touched": sorted(domain_switches),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": cache_hit_rate,
        "avg_compilation_ms": avg_compilation_ms,
        "quality_trend": quality_trend,
        "total_events": len(events),
    }

    # Write summary
    write_json_atomic(_summary_path(workspace_root), summary)
    return summary


# ── Helpers ─────────────────────────────────────────────────────


def _load_events(workspace_root: Path) -> list[dict[str, Any]]:
    """Load all events from JSONL file."""
    path = _events_path(workspace_root)
    if not path.exists():
        return []
    events = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    except Exception as exc:
        logger.warning("Failed to load events: %s", exc)
    return events
