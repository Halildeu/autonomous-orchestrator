from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


_WORK_INTAKE_TOP_NEXT_REQUIRED = {
    "intake_id",
    "bucket",
    "severity",
    "priority",
    "status",
    "title",
    "source_type",
    "source_ref",
}

_WORK_INTAKE_TOP_NEXT_ALLOWED = {
    *sorted(_WORK_INTAKE_TOP_NEXT_REQUIRED),
    "autopilot_allowed",
    "autopilot_notes",
    "autopilot_reason",
    "autopilot_selected",
    "suggested_extension",
    "lens_id",
    "lens_reason",
}


def _sanitize_work_intake_top_next_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        cleaned: dict[str, Any] = {}
        for field in sorted(_WORK_INTAKE_TOP_NEXT_ALLOWED):
            item = raw.get(field)
            if field in _WORK_INTAKE_TOP_NEXT_REQUIRED:
                if isinstance(item, str) and item:
                    cleaned[field] = item
                continue
            if field in {"autopilot_allowed", "autopilot_selected"}:
                if isinstance(item, bool):
                    cleaned[field] = item
                continue
            if field in {"autopilot_notes", "suggested_extension"}:
                if isinstance(item, list):
                    vals = [str(x) for x in item if isinstance(x, str) and x]
                    if vals:
                        cleaned[field] = vals
                continue
            if isinstance(item, str) and item:
                cleaned[field] = item
        if _WORK_INTAKE_TOP_NEXT_REQUIRED.issubset(set(cleaned.keys())):
            out.append(cleaned)
    return out


def _work_intake_section(workspace_root: Path) -> dict[str, Any] | None:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        return None
    rel_path = str(Path(".cache") / "index" / "work_intake.v1.json")
    try:
        obj = _load_json(intake_path)
    except Exception:
        return {
            "status": "WARN",
            "work_intake_path": rel_path,
            "items_count": 0,
            "counts_by_bucket": {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0},
            "top_next_actions": [],
            "next_intake_focus": "NONE",
            "by_bucket": {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0},
            "top_next": [],
        }
    items = obj.get("items") if isinstance(obj, dict) else None
    summary = obj.get("summary") if isinstance(obj, dict) else None
    items_count = len(items) if isinstance(items, list) else 0
    counts_by_bucket = summary.get("counts_by_bucket") if isinstance(summary, dict) else None
    top_next_actions_raw = summary.get("top_next_actions") if isinstance(summary, dict) else None
    next_focus = summary.get("next_intake_focus") if isinstance(summary, dict) else None
    active_count = summary.get("active_count") if isinstance(summary, dict) else None
    historical_done_count = summary.get("historical_done_count") if isinstance(summary, dict) else None
    by_bucket = summary.get("by_bucket") if isinstance(summary, dict) else None
    top_next = summary.get("top_next") if isinstance(summary, dict) else None
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = status if status in {"OK", "WARN", "IDLE"} else "WARN"
    if not isinstance(counts_by_bucket, dict):
        counts_by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    top_next_actions = _sanitize_work_intake_top_next_actions(top_next_actions_raw)
    if not isinstance(next_focus, str):
        next_focus = "NONE"
    if not isinstance(by_bucket, dict):
        by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    if not isinstance(top_next, list):
        top_next = []
    return {
        "status": status_str,
        "work_intake_path": rel_path,
        "items_count": int(items_count),
        "active_items_count": int(active_count) if isinstance(active_count, int) and active_count >= 0 else int(items_count),
        "historical_done_count": int(historical_done_count)
        if isinstance(historical_done_count, int) and historical_done_count >= 0
        else 0,
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions[:5],
        "next_intake_focus": next_focus,
        "by_bucket": by_bucket,
        "top_next": top_next[:5],
    }


def _work_intake_exec_section(workspace_root: Path) -> dict[str, Any] | None:
    exec_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not exec_path.exists():
        return None
    rel_path = str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json")
    try:
        obj = _load_json(exec_path)
    except Exception:
        return {
            "status": "WARN",
            "exec_report_path": rel_path,
            "policy_source": "missing",
            "policy_hash": "",
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
        }
    policy_source = str(obj.get("policy_source") or "missing") if isinstance(obj, dict) else "missing"
    policy_hash = str(obj.get("policy_hash") or "") if isinstance(obj, dict) else ""
    applied_count = int(obj.get("applied_count") or 0) if isinstance(obj, dict) else 0
    planned_count = int(obj.get("planned_count") or 0) if isinstance(obj, dict) else 0
    idle_count = int(obj.get("idle_count") or 0) if isinstance(obj, dict) else 0
    ignored_count = int(obj.get("ignored_count") or 0) if isinstance(obj, dict) else 0
    ignored_by_reason = obj.get("ignored_by_reason") if isinstance(obj, dict) else None
    skipped_count = int(obj.get("skipped_count") or 0) if isinstance(obj, dict) else 0
    decision_needed_count = int(obj.get("decision_needed_count") or 0) if isinstance(obj, dict) else 0
    decision_inbox_path = obj.get("decision_inbox_path") if isinstance(obj, dict) else None
    skipped_by_reason = obj.get("skipped_by_reason") if isinstance(obj, dict) else None
    status = "OK" if policy_hash else "WARN"
    payload: dict[str, Any] = {
        "status": status,
        "exec_report_path": rel_path,
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "applied_count": applied_count,
        "planned_count": planned_count,
        "idle_count": idle_count,
    }
    if skipped_count:
        payload["skipped_count"] = skipped_count
    if ignored_count:
        payload["ignored_count"] = ignored_count
    if decision_needed_count:
        payload["decision_needed_count"] = decision_needed_count
    if isinstance(decision_inbox_path, str) and decision_inbox_path:
        payload["decision_inbox_path"] = decision_inbox_path
    if isinstance(skipped_by_reason, dict):
        payload["skipped_by_reason"] = {
            str(k): int(v) for k, v in skipped_by_reason.items() if isinstance(v, int) and v >= 0
        }
    if isinstance(ignored_by_reason, dict):
        payload["ignored_by_reason"] = {
            str(k): int(v) for k, v in ignored_by_reason.items() if isinstance(v, int) and v >= 0
        }
    return payload


def _doer_loop_section(workspace_root: Path) -> dict[str, Any]:
    lock_path = workspace_root / ".cache" / "doer" / "doer_loop_lock.v1.json"
    clear_path = workspace_root / ".cache" / "reports" / "doer_loop_lock_clear_stale.v1.json"
    rel_lock = str(Path(".cache") / "doer" / "doer_loop_lock.v1.json")
    payload: dict[str, Any] = {"lock_state": "MISSING", "lock_path": rel_lock}
    if lock_path.exists():
        try:
            obj = _load_json(lock_path)
        except Exception:
            obj = {}
        payload["lock_state"] = "LOCKED"
        if isinstance(obj, dict):
            payload["owner_tag"] = str(obj.get("owner_tag") or "")
            payload["expires_at"] = str(obj.get("expires_at") or "")
            payload["last_run_id"] = str(obj.get("run_id") or "")
        return payload
    if clear_path.exists():
        payload["lock_state"] = "STALE_CLEARED"
    return payload


def _decisions_section(workspace_root: Path) -> dict[str, Any] | None:
    inbox_path = workspace_root / ".cache" / "index" / "decision_inbox.v1.json"
    rel_path = str(Path(".cache") / "index" / "decision_inbox.v1.json")
    pending_count = 0
    pending_by_kind: dict[str, int] = {}
    seed_pending_count = 0
    if inbox_path.exists():
        try:
            obj = _load_json(inbox_path)
        except Exception:
            obj = {}
        items = obj.get("items") if isinstance(obj, dict) else None
        items_list = items if isinstance(items, list) else []
        counts = obj.get("counts") if isinstance(obj, dict) else None
        by_kind = counts.get("by_kind") if isinstance(counts, dict) else None
        if isinstance(by_kind, dict):
            pending_by_kind = {str(k): int(v) for k, v in by_kind.items() if isinstance(v, int) and v >= 0}
        pending_count = int(counts.get("total") or 0) if isinstance(counts, dict) else len(items_list)
        for item in items_list:
            if isinstance(item, dict) and str(item.get("why_blocked") or "") == "DECISION_SEED":
                seed_pending_count += 1
    blocked_count = pending_count

    decisions_applied_path = workspace_root / ".cache" / "index" / "decisions_applied.v1.jsonl"
    last_apply_path = None
    if decisions_applied_path.exists():
        last_apply_path = str(Path(".cache") / "index" / "decisions_applied.v1.jsonl")

    payload = {
        "last_decision_inbox_path": rel_path,
        "blocked_count": blocked_count,
        "pending_decisions_count": pending_count,
        "pending_decisions_by_kind": {k: pending_by_kind[k] for k in sorted(pending_by_kind)},
        "seed_pending_count": int(seed_pending_count),
    }
    if last_apply_path:
        payload["last_decision_apply_path"] = last_apply_path
    return payload
