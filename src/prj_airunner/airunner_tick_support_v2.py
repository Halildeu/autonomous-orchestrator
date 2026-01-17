from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.prj_airunner.airunner_tick_utils import _active_hours_snapshot


def build_active_hours_context(
    *, schedule: dict[str, Any], now: datetime, force_active_hours: bool
) -> tuple[bool, list[str], Callable[[str], dict[str, Any]]]:
    active_snapshot = _active_hours_snapshot(schedule, now)
    active_hours_enabled = bool(active_snapshot.get("active_hours_enabled", False))
    outside_hours_mode_effective = str(active_snapshot.get("outside_hours_mode_effective") or "poll_only")
    inside_hours_raw = bool(active_snapshot.get("inside_active_hours", True))
    inside_hours_effective = inside_hours_raw
    schedule_notes = list(active_snapshot.get("notes") or [])
    if outside_hours_mode_effective == "ignore":
        inside_hours_effective = True
        schedule_notes.append("outside_hours_mode_ignore")
    if force_active_hours:
        inside_hours_effective = True
        active_snapshot["inside_active_hours"] = True
        schedule_notes.append("force_active_hours=true")

    def _active_meta(reason: str) -> dict[str, Any]:
        return {
            "active_hours_enabled": bool(active_hours_enabled),
            "active_hours_tz": str(active_snapshot.get("active_hours_tz") or ""),
            "now_local_hhmm": str(active_snapshot.get("now_local_hhmm") or ""),
            "inside_active_hours": bool(inside_hours_raw),
            "inside_active_hours_effective": bool(inside_hours_effective),
            "outside_hours_mode_effective": str(outside_hours_mode_effective),
            "gate_reason": reason,
        }

    outside_hours = bool(active_hours_enabled) and not inside_hours_effective and outside_hours_mode_effective != "ignore"
    return outside_hours, schedule_notes, _active_meta


def seed_network_live_decision(
    *,
    workspace_root: Path,
    evidence_paths: list[str],
    ops_called: list[str],
    notes: list[str],
    reason: str,
) -> None:
    try:
        from src.ops.decision_inbox import run_decision_inbox_build, run_decision_seed
    except Exception:
        return
    try:
        seed_res = run_decision_seed(
            workspace_root=workspace_root,
            decision_kind="NETWORK_LIVE_ENABLE",
            target="NETWORK_LIVE",
        )
    except Exception:
        return
    seed_path = seed_res.get("seed_path") if isinstance(seed_res, dict) else ""
    if isinstance(seed_path, str) and seed_path:
        evidence_paths.append(seed_path)
    try:
        inbox_res = run_decision_inbox_build(workspace_root=workspace_root)
    except Exception:
        inbox_res = None
    if isinstance(inbox_res, dict):
        inbox_path = inbox_res.get("decision_inbox_path")
        if isinstance(inbox_path, str) and inbox_path:
            evidence_paths.append(inbox_path)
        ops_called.append("decision-inbox-build")
    notes.append(f"network_live_decision_seed={reason}")
