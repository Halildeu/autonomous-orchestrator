"""Rule effectiveness tracker — per-rule usage scoring and tier classification.

Tracks how often each rule is loaded, applied, violated, or ignored.
Classifies rules into HOT/WARM/COLD/DEAD tiers for memory optimization.

State: .cache/reports/rule_effectiveness.v1.json
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.shared.utils import load_json_or_default, now_iso8601, write_json_atomic

logger = logging.getLogger(__name__)

# Tier thresholds
_HOT_THRESHOLD = 0.7
_WARM_THRESHOLD = 0.3
_DEAD_SESSION_COUNT = 30


def _state_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "rule_effectiveness.v1.json"


def _load_state(workspace_root: Path) -> dict[str, Any]:
    return load_json_or_default(_state_path(workspace_root), {"version": "v1", "rules": {}, "session_count": 0})


def _save_state(workspace_root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso8601()
    path = _state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, state)


# ── Public API ──────────────────────────────────────────────────


def track_rule_usage(
    workspace_root: Path,
    *,
    rule_id: str,
    action: str,  # "loaded", "applied", "violated", "ignored"
) -> None:
    """Record a single rule usage event."""
    state = _load_state(workspace_root)
    rules = state.get("rules", {})

    if rule_id not in rules:
        rules[rule_id] = {
            "total_loads": 0,
            "times_applied": 0,
            "times_violated": 0,
            "times_ignored": 0,
            "first_seen": now_iso8601(),
            "last_loaded": None,
            "last_applied": None,
        }

    entry = rules[rule_id]
    now = now_iso8601()

    if action == "loaded":
        entry["total_loads"] += 1
        entry["last_loaded"] = now
    elif action == "applied":
        entry["times_applied"] += 1
        entry["last_applied"] = now
    elif action == "violated":
        entry["times_violated"] += 1
    elif action == "ignored":
        entry["times_ignored"] += 1

    rules[rule_id] = entry
    state["rules"] = rules
    _save_state(workspace_root, state)


def increment_session_count(workspace_root: Path) -> int:
    """Increment session counter (call once per session)."""
    state = _load_state(workspace_root)
    state["session_count"] = state.get("session_count", 0) + 1
    _save_state(workspace_root, state)
    return state["session_count"]


def compute_effectiveness(workspace_root: Path) -> list[dict[str, Any]]:
    """Compute effectiveness score and tier for all tracked rules."""
    state = _load_state(workspace_root)
    rules = state.get("rules", {})
    session_count = state.get("session_count", 1)
    results = []

    for rule_id, entry in rules.items():
        loads = entry.get("total_loads", 0)
        applied = entry.get("times_applied", 0)
        violated = entry.get("times_violated", 0)
        ignored = entry.get("times_ignored", 0)

        # Effectiveness = (applied + violated_prevented) / total_loads
        # violated counts as "rule was relevant" (it caught something)
        relevant = applied + violated
        score = round(relevant / max(loads, 1), 4)

        # Tier classification
        tier = classify_tier(score, loads, session_count)

        results.append({
            "rule_id": rule_id,
            "total_loads": loads,
            "times_applied": applied,
            "times_violated": violated,
            "times_ignored": ignored,
            "effectiveness_score": score,
            "tier": tier,
            "last_applied": entry.get("last_applied"),
            "last_loaded": entry.get("last_loaded"),
        })

    # Sort by effectiveness descending
    results.sort(key=lambda r: r["effectiveness_score"], reverse=True)
    return results


def classify_tier(score: float, loads: int, session_count: int) -> str:
    """Classify rule into HOT/WARM/COLD/DEAD tier."""
    if loads == 0 and session_count >= _DEAD_SESSION_COUNT:
        return "DEAD"
    if score >= _HOT_THRESHOLD:
        return "HOT"
    if score >= _WARM_THRESHOLD:
        return "WARM"
    if loads == 0:
        return "COLD"
    return "COLD"


def get_rules_by_tier(workspace_root: Path) -> dict[str, list[str]]:
    """Get rule IDs grouped by tier."""
    results = compute_effectiveness(workspace_root)
    tiers: dict[str, list[str]] = {"HOT": [], "WARM": [], "COLD": [], "DEAD": []}
    for r in results:
        tiers[r["tier"]].append(r["rule_id"])
    return tiers
