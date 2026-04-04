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

from src.shared.utils import write_json_atomic

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
    write_json_atomic(out_path, report)

    return report


# ── ACE Evolution Engine (Phase 5) ─────────────────────────────
# Agentic Context Engineering: produce → reflect → curate cycle.
# Full autonomous: confidence >= 0.9 auto-applies, < 0.7 needs human review.

_AUTO_APPLY_THRESHOLD = 0.9
_AUTO_WITH_ROLLBACK_THRESHOLD = 0.7
_PROPOSALS_PATH = ".cache/reports/context_evolution_proposals.v1.json"


def run_evolution_cycle(
    workspace_root: Path,
) -> dict[str, Any]:
    """ACE cycle: analyze rule effectiveness, generate evolution proposals.

    1. Produce: load rule_effectiveness + session_metrics
    2. Reflect: identify prune/promote/demote candidates
    3. Curate: generate proposals, auto-apply if confidence >= 0.9
    """
    now = _now_iso()
    proposals: list[dict[str, Any]] = []

    # 1. Produce — load effectiveness data
    try:
        from src.ops.rule_effectiveness import compute_effectiveness, get_rules_by_tier
        effectiveness = compute_effectiveness(workspace_root)
        tiers = get_rules_by_tier(workspace_root)
    except Exception:
        return {"version": "v1", "generated_at": now, "status": "SKIP", "reason": "effectiveness_unavailable", "proposals": []}

    # 2. Reflect — identify candidates
    for rule in effectiveness:
        rule_id = rule["rule_id"]
        score = rule["effectiveness_score"]
        tier = rule["tier"]
        loads = rule["total_loads"]

        # DEAD rules → prune with high confidence
        if tier == "DEAD":
            proposals.append(_make_proposal(
                rule_id=rule_id,
                proposal_type="prune",
                reason=f"Never loaded in {loads} loads across sessions",
                confidence=0.95,
            ))

        # COLD rules with many loads but no application → demote
        elif tier == "COLD" and loads >= 10 and score < 0.1:
            proposals.append(_make_proposal(
                rule_id=rule_id,
                proposal_type="demote",
                reason=f"Loaded {loads} times, effectiveness={score:.2f} — rarely relevant",
                confidence=0.85,
            ))

        # HOT rules that were WARM → promote
        elif tier == "HOT" and score >= 0.8:
            proposals.append(_make_proposal(
                rule_id=rule_id,
                proposal_type="promote",
                reason=f"Consistently effective: score={score:.2f}, loads={loads}",
                confidence=0.90,
            ))

    # 3. Curate — auto-apply or queue for review
    auto_applied: list[str] = []
    for proposal in proposals:
        conf = proposal["confidence"]
        if conf >= _AUTO_APPLY_THRESHOLD:
            proposal["auto_applied"] = True
            proposal["applied_at"] = now
            auto_applied.append(proposal["proposal_id"])
        elif conf >= _AUTO_WITH_ROLLBACK_THRESHOLD:
            proposal["auto_applied"] = True
            proposal["applied_at"] = now
            proposal["rollback_available"] = True
            auto_applied.append(proposal["proposal_id"])
        else:
            proposal["auto_applied"] = False
            proposal["requires_human_review"] = True

    result = {
        "version": "v1",
        "generated_at": now,
        "status": "OK",
        "total_rules_analyzed": len(effectiveness),
        "proposals_count": len(proposals),
        "auto_applied_count": len(auto_applied),
        "proposals": proposals,
        "tier_summary": {tier: len(ids) for tier, ids in tiers.items()},
    }

    # Write proposals
    out = workspace_root / _PROPOSALS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out, result)

    return result


def _make_proposal(
    *,
    rule_id: str,
    proposal_type: str,
    reason: str,
    confidence: float,
) -> dict[str, Any]:
    """Create an evolution proposal."""
    import hashlib
    date_part = _now_iso()[:10].replace("-", "")
    hash_part = hashlib.sha256(f"{rule_id}:{proposal_type}:{date_part}".encode()).hexdigest()[:6]
    return {
        "proposal_id": f"EVO-{date_part}-{hash_part}",
        "type": proposal_type,
        "target_rule": rule_id,
        "reason": reason,
        "confidence": round(confidence, 4),
        "auto_applied": False,
    }
