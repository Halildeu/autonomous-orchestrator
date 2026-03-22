"""Fact evolution tracking and regression detection.

Analyzes decision history to detect value regressions (revert to previous value)
and build change frequency reports.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.session.context_store import SessionContextError, SessionPaths, load_context


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def detect_fact_regressions(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect decisions whose current value matches a previous historical value (regression)."""
    regressions: list[dict[str, Any]] = []
    decisions = context.get("ephemeral_decisions", [])
    if not isinstance(decisions, list):
        return regressions

    for d in decisions:
        if not isinstance(d, dict):
            continue
        history = d.get("history")
        if not isinstance(history, list) or not history:
            continue

        current_val = json.dumps(d.get("value"), sort_keys=True, ensure_ascii=True)
        for h in history:
            if not isinstance(h, dict):
                continue
            hist_val = json.dumps(h.get("value"), sort_keys=True, ensure_ascii=True)
            if hist_val == current_val:
                regressions.append({
                    "key": str(d.get("key") or ""),
                    "current_value": d.get("value"),
                    "reverted_to_value_from": str(h.get("changed_at") or ""),
                    "history_length": len(history),
                })
                break

    return regressions


def build_fact_evolution_report(
    *,
    workspace_root: Path,
    session_id: str = "default",
) -> dict[str, Any]:
    """Build fact evolution report: decisions with history, regressions, change frequency."""
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    now = _now_iso()

    if not sp.context_path.exists():
        return {"version": "v1", "generated_at": now, "status": "SKIP", "reason": "session_not_found"}

    try:
        ctx = load_context(sp.context_path)
    except SessionContextError:
        return {"version": "v1", "generated_at": now, "status": "SKIP", "reason": "session_load_failed"}

    decisions = ctx.get("ephemeral_decisions", [])
    if not isinstance(decisions, list):
        decisions = []

    decisions_with_history = [d for d in decisions if isinstance(d, dict) and isinstance(d.get("history"), list) and d.get("history")]
    regressions = detect_fact_regressions(ctx)

    total_changes = sum(len(d.get("history", [])) for d in decisions_with_history)

    report = {
        "version": "v1",
        "generated_at": now,
        "status": "WARN" if regressions else "OK",
        "total_decisions": len(decisions),
        "decisions_with_history": len(decisions_with_history),
        "total_changes": total_changes,
        "regressions": regressions,
        "regression_count": len(regressions),
    }

    out_path = workspace_root / ".cache" / "reports" / "fact_evolution_report.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return report
