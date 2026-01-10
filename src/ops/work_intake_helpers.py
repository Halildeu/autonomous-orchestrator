from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _suggested_extensions(source: dict[str, Any], bucket: str) -> list[str]:
    source_type = str(source.get("source_type") or "")
    if source_type == "GITHUB_OPS":
        return ["PRJ-GITHUB-OPS"]
    if bucket == "PROJECT" and source_type == "RELEASE":
        return ["PRJ-RELEASE-AUTOMATION"]
    if source_type == "JOB_STATUS":
        job_type = str(source.get("job_type") or "")
        job_status = str(source.get("job_status") or "")
        if job_type == "SMOKE_FULL" and job_status in {"FAIL", "TIMEOUT", "KILLED"}:
            return ["PRJ-AIRUNNER"]
        if job_type.startswith("RELEASE_"):
            return ["PRJ-RELEASE-AUTOMATION"]
    if source_type == "LENS_GAP":
        lens_id = str(source.get("lens_id") or "")
        lens_reason = str(source.get("lens_reason") or "")
        if lens_id == "operability":
            if lens_reason in {"soft_exceeded_gt", "hard_exceeded_gt"}:
                return ["PRJ-M0-MAINTAINABILITY"]
            if lens_reason in {
                "jobs_stuck_gt",
                "jobs_fail_gt",
                "pdca_cursor_stale_hours_gt",
                "heartbeat_stale_seconds_gt",
                "intake_new_items_per_day_gt",
                "suppressed_per_day_gt",
            }:
                return ["PRJ-AIRUNNER"]
    if bucket != "TICKET":
        return []
    if source_type == "TIME_SINK":
        return ["PRJ-AIRUNNER"]
    if source_type in {"MANUAL_REQUEST", "DOC_NAV"}:
        return ["PRJ-AIRUNNER"]
    if source_type == "SCRIPT_BUDGET":
        path = str(source.get("path") or source.get("source_ref") or "")
        if path.startswith("ci/"):
            return ["PRJ-AIRUNNER"]
    return []


def _normalize_evidence(paths: list[str], workspace_root: Path) -> list[str]:
    cleaned: list[str] = []
    for p in paths:
        if not isinstance(p, str) or not p.strip():
            continue
        abs_path = (workspace_root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
        rel = _rel_to_workspace(abs_path, workspace_root)
        if rel:
            cleaned.append(rel)
    return sorted(set(cleaned))


def _load_exec_ticket_applied_ids(workspace_root: Path, notes: list[str]) -> set[str]:
    report_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not report_path.exists():
        notes.append("work_intake_exec_missing")
        return set()
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("work_intake_exec_invalid")
        return set()
    entries = obj.get("entries") if isinstance(obj, dict) else None
    if not isinstance(entries, list):
        notes.append("work_intake_exec_empty")
        return set()
    applied: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "") != "APPLIED":
            continue
        intake_id = entry.get("intake_id")
        if isinstance(intake_id, str) and intake_id:
            applied.add(intake_id)
    return applied
