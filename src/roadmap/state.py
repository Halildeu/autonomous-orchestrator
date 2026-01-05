from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def default_state(*, roadmap_path: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "version": "v1",
        "roadmap_path": str(roadmap_path),
        "workspace_root": str(workspace_root),
        "roadmap_sha256": "0" * 64,
        "last_roadmap_sha256": None,
        "drift_detected": False,
        "completed_milestones_meta": {},
        "bootstrapped": False,
        "paused": False,
        "paused_at": None,
        "pause_reason": None,
        "current_step_id": None,
        "last_completed_step_id": None,
        "last_gate_ok": None,
        "completed_milestones": [],
        "current_milestone": None,
        "attempts": {},
        "last_result": {"status": "OK", "milestone": None, "evidence_path": None, "error_code": None},
        "quarantine": {"milestone": None, "until": None, "reason": None},
        "backoff": {"seconds": 0, "next_try_at": None},
    }


@dataclass(frozen=True)
class StateLoadResult:
    state: dict[str, Any]
    existed: bool


def load_state(*, state_path: Path, schema_path: Path, roadmap_path: Path, workspace_root: Path) -> StateLoadResult:
    if not state_path.exists():
        return StateLoadResult(state=default_state(roadmap_path=roadmap_path, workspace_root=workspace_root), existed=False)

    obj = _load_json(state_path)
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        msgs = []
        for err in errors[:25]:
            where = err.json_path or "$"
            msgs.append(f"{where}: {err.message}")
        raise ValueError("STATE_SCHEMA_INVALID: " + "; ".join(msgs))

    # Ensure state is bound to the current roadmap/workspace; if not, fail-closed.
    if obj.get("roadmap_path") != str(roadmap_path) or obj.get("workspace_root") != str(workspace_root):
        raise ValueError("STATE_MISMATCH: state file does not match roadmap_path/workspace_root")

    return StateLoadResult(state=obj, existed=True)


def save_state(*, state_path: Path, state: dict[str, Any]) -> None:
    _save_json(state_path, state)


def is_quarantined(state: dict[str, Any], *, now: datetime) -> bool:
    q = state.get("quarantine") if isinstance(state, dict) else None
    if not isinstance(q, dict):
        return False
    until_s = q.get("until")
    if not isinstance(until_s, str):
        return False
    until_dt = _parse_iso8601(until_s)
    if until_dt is None:
        return False
    return until_dt > now


def is_in_backoff(state: dict[str, Any], *, now: datetime) -> bool:
    b = state.get("backoff") if isinstance(state, dict) else None
    if not isinstance(b, dict):
        return False
    next_try = b.get("next_try_at")
    if not isinstance(next_try, str):
        return False
    next_try_dt = _parse_iso8601(next_try)
    if next_try_dt is None:
        return False
    return next_try_dt > now


def set_backoff(state: dict[str, Any], *, seconds: int, now: datetime) -> None:
    next_try = now + timedelta(seconds=seconds)
    state["backoff"] = {"seconds": int(seconds), "next_try_at": next_try.isoformat().replace("+00:00", "Z")}


def clear_backoff(state: dict[str, Any]) -> None:
    state["backoff"] = {"seconds": 0, "next_try_at": None}


def quarantine_milestone(state: dict[str, Any], *, milestone_id: str, now: datetime, reason: str) -> None:
    until = now + timedelta(days=1)
    state["quarantine"] = {"milestone": milestone_id, "until": until.isoformat().replace("+00:00", "Z"), "reason": str(reason)}


def clear_quarantine(state: dict[str, Any]) -> None:
    state["quarantine"] = {"milestone": None, "until": None, "reason": None}


def bump_attempt(state: dict[str, Any], milestone_id: str) -> int:
    attempts = state.setdefault("attempts", {})
    if not isinstance(attempts, dict):
        attempts = {}
        state["attempts"] = attempts
    current = attempts.get(milestone_id, 0)
    try:
        current_i = int(current)
    except Exception:
        current_i = 0
    new_v = current_i + 1
    attempts[milestone_id] = new_v
    return new_v


def record_last_result(
    state: dict[str, Any], *, status: str, milestone_id: str | None, evidence_path: str | None, error_code: str | None
) -> None:
    state["last_result"] = {
        "status": status,
        "milestone": milestone_id,
        "evidence_path": evidence_path,
        "error_code": error_code,
    }


def set_current_milestone(state: dict[str, Any], milestone_id: str | None) -> None:
    state["current_milestone"] = milestone_id


def mark_completed(state: dict[str, Any], milestone_id: str) -> None:
    completed = state.setdefault("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []
        state["completed_milestones"] = completed
    if milestone_id not in completed:
        completed.append(milestone_id)

    # Record completion metadata for drift detection.
    sha = state.get("roadmap_sha256")
    if not isinstance(sha, str) or not sha:
        return
    meta = state.setdefault("completed_milestones_meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["completed_milestones_meta"] = meta
    meta[milestone_id] = {"roadmap_sha256_at_completion": sha, "completed_at": _now_iso8601()}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return _now_iso8601()

def set_checkpoint(
    state: dict[str, Any],
    *,
    current_step_id: str | None = None,
    last_completed_step_id: str | None = None,
    last_gate_ok: bool | None = None,
) -> None:
    state["current_step_id"] = current_step_id
    state["last_completed_step_id"] = last_completed_step_id
    state["last_gate_ok"] = last_gate_ok


def pause_state(state: dict[str, Any], *, reason: str, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    state["paused"] = True
    state["paused_at"] = now.isoformat().replace("+00:00", "Z")
    state["pause_reason"] = str(reason)[:300]


def resume_state(state: dict[str, Any]) -> None:
    state["paused"] = False
    state["paused_at"] = None
    state["pause_reason"] = None


def bootstrap_completed_milestones(*, state: dict[str, Any], workspace_root: Path) -> list[str]:
    """
    Best-effort, deterministic state bootstrap from workspace artifacts.
    Fail-closed rule: only mark a milestone completed if ALL required markers exist.
    """

    completed_raw = state.get("completed_milestones", [])
    completed: list[str] = [str(x) for x in completed_raw] if isinstance(completed_raw, list) else []

    required_by_ms: dict[str, list[str]] = {
        "M0": [
            "tenant/TENANT-DEFAULT/.gitkeep",
            "formats/.gitkeep",
            "packs/.gitkeep",
            "best_practices/.gitkeep",
            "incubator/.gitkeep",
        ],
        "M1": [
            "tenant/TENANT-DEFAULT/context.v1.md",
            "tenant/TENANT-DEFAULT/stakeholders.v1.md",
            "tenant/TENANT-DEFAULT/scope.v1.md",
            "tenant/TENANT-DEFAULT/criteria.v1.md",
        ],
        "M2": [
            "schemas/tenant-decision-bundle.schema.json",
            "tenant/TENANT-DEFAULT/decision-bundle.v1.json",
            "ci/validate_tenant_consistency.py",
        ],
        "M3.5": [
            ".cache/sessions/default/session_context.v1.json",
        ],
        "M8.2": [
            ".cache/promotion/promotion_bundle.v1.zip",
            ".cache/promotion/promotion_report.v1.json",
            ".cache/promotion/core_patch_summary.v1.md",
        ],
    }

    known = ["M0", "M1", "M2", "M3.5", "M8.2"]
    detected_complete: dict[str, bool] = {}
    partial: list[str] = []
    inconsistent: list[str] = []

    for ms_id in known:
        req = required_by_ms[ms_id]
        present = [p for p in req if (workspace_root / p).exists()]
        missing = [p for p in req if not (workspace_root / p).exists()]
        detected_complete[ms_id] = len(missing) == 0
        if present and missing:
            partial.append(ms_id)
        if ms_id in completed and not detected_complete[ms_id]:
            inconsistent.append(ms_id)

    # Preserve progress for unknown milestones; replace only known milestones.
    other_completed = [m for m in completed if m not in set(known)]
    new_completed: list[str] = []
    seen: set[str] = set()

    for m in other_completed:
        if m not in seen:
            new_completed.append(m)
            seen.add(m)

    for ms_id in known:
        if detected_complete.get(ms_id, False) and ms_id not in seen:
            new_completed.append(ms_id)
            seen.add(ms_id)

    state["completed_milestones"] = new_completed
    state["bootstrapped"] = True

    # Ensure drift metadata exists for bootstrapped milestones (v0.1).
    for ms_id in known:
        if detected_complete.get(ms_id, False):
            mark_completed(state, ms_id)

    warnings: list[str] = []
    if inconsistent:
        warnings.append("BOOTSTRAP_INCONSISTENT:" + ",".join(sorted(inconsistent)))
    if partial:
        warnings.append("BOOTSTRAP_PARTIAL:" + ",".join(sorted(partial)))
    if warnings:
        record_last_result(state, status="OK", milestone_id=None, evidence_path=None, error_code=warnings[0])

    return warnings
