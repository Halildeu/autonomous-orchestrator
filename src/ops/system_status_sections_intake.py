from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    top_next_actions = summary.get("top_next_actions") if isinstance(summary, dict) else None
    next_focus = summary.get("next_intake_focus") if isinstance(summary, dict) else None
    by_bucket = summary.get("by_bucket") if isinstance(summary, dict) else None
    top_next = summary.get("top_next") if isinstance(summary, dict) else None
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = status if status in {"OK", "WARN", "IDLE"} else "WARN"
    if not isinstance(counts_by_bucket, dict):
        counts_by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    if not isinstance(top_next_actions, list):
        top_next_actions = []
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
    status = "OK" if policy_hash else "WARN"
    return {
        "status": status,
        "exec_report_path": rel_path,
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "applied_count": applied_count,
        "planned_count": planned_count,
        "idle_count": idle_count,
    }
