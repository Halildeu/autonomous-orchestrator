from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.prj_airunner.airunner_tick import _load_policy, run_airunner_tick
from src.prj_airunner.airunner_tick_utils import (
    _dump_json,
    _heartbeat_age_seconds,
    _load_heartbeat,
    _load_json,
    _load_lock,
    _lock_paths,
    _now_iso,
    _parse_iso,
    _rel_to_workspace,
    _release_lock,
)


def run_airunner_status(*, workspace_root: Path) -> dict[str, Any]:
    report_path = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    if not report_path.exists():
        return {
            "status": "IDLE",
            "error_code": "NO_TICK_REPORT",
            "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
            "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        }
    try:
        report = _load_json(report_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "TICK_REPORT_INVALID",
            "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
            "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        }
    status = report.get("status") if isinstance(report, dict) else "WARN"
    return {
        "status": status,
        "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json")
        if heartbeat_path.exists()
        else "",
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json") if lock_path.exists() else "",
        "tick_id": report.get("tick_id") if isinstance(report, dict) else None,
        "policy_source": report.get("policy_source") if isinstance(report, dict) else None,
        "policy_hash": report.get("policy_hash") if isinstance(report, dict) else None,
    }


def run_airunner_lock_status(*, workspace_root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    lock = _load_lock(lock_path)
    heartbeat = _load_heartbeat(heartbeat_path)
    heartbeat_age = _heartbeat_age_seconds(heartbeat, now)
    lock_state = "LOCKED" if isinstance(lock, dict) else "MISSING"
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "lock_state": lock_state,
        "lock_present": bool(lock),
        "lock_expires_at": str(lock.get("expires_at") or "") if isinstance(lock, dict) else "",
        "heartbeat_present": bool(heartbeat),
        "heartbeat_age_seconds": heartbeat_age,
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
        "notes": ["PROGRAM_LED=true", "NETWORK=false"],
    }
    report_path = workspace_root / ".cache" / "reports" / "airunner_lock_status.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(payload), encoding="utf-8")
    rel_report = _rel_to_workspace(report_path, workspace_root) or str(report_path)
    return {
        "status": "OK",
        "report_path": rel_report,
        "lock_state": lock_state,
        "heartbeat_age_seconds": heartbeat_age,
    }


def run_airunner_lock_clear_stale(*, workspace_root: Path, max_age_seconds: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    lock = _load_lock(lock_path)
    heartbeat = _load_heartbeat(heartbeat_path)
    heartbeat_age = _heartbeat_age_seconds(heartbeat, now)
    lock_state_before = "LOCKED" if isinstance(lock, dict) else "MISSING"
    status = "IDLE"
    reason = "NO_LOCK"
    cleared = False
    if isinstance(lock, dict):
        if heartbeat_age is None:
            _release_lock(lock_path)
            cleared = True
            status = "OK"
            reason = "HEARTBEAT_MISSING"
        elif heartbeat_age > int(max_age_seconds):
            _release_lock(lock_path)
            cleared = True
            status = "OK"
            reason = "HEARTBEAT_STALE"
        else:
            status = "IDLE"
            reason = "HEARTBEAT_FRESH"
    lock_state_after = "MISSING" if cleared else lock_state_before
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "reason": reason,
        "lock_state_before": lock_state_before,
        "lock_state_after": lock_state_after,
        "lock_cleared": cleared,
        "heartbeat_age_seconds": heartbeat_age,
        "max_age_seconds": int(max_age_seconds),
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
        "notes": ["PROGRAM_LED=true", "NETWORK=false"],
    }
    report_path = workspace_root / ".cache" / "reports" / "airunner_lock_clear.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(payload), encoding="utf-8")
    rel_report = _rel_to_workspace(report_path, workspace_root) or str(report_path)
    return {
        "status": status,
        "report_path": rel_report,
        "lock_cleared": cleared,
        "lock_state_before": lock_state_before,
        "lock_state_after": lock_state_after,
        "heartbeat_age_seconds": heartbeat_age,
    }


def _watchdog_state_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "airunner" / "airrunner_watchdog.v1.json"


def _load_watchdog_state(workspace_root: Path) -> dict[str, Any]:
    path = _watchdog_state_path(workspace_root)
    if not path.exists():
        return {"version": "v1", "date": "", "recoveries": 0, "notes": []}
    try:
        obj = _load_json(path)
    except Exception:
        return {"version": "v1", "date": "", "recoveries": 0, "notes": ["state_invalid"]}
    return obj if isinstance(obj, dict) else {"version": "v1", "date": "", "recoveries": 0, "notes": ["state_invalid"]}


def _write_watchdog_state(workspace_root: Path, state: dict[str, Any]) -> str:
    path = _watchdog_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(state), encoding="utf-8")
    return _rel_to_workspace(path, workspace_root) or str(path)


def run_airunner_watchdog(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    watchdog = policy.get("watchdog") if isinstance(policy.get("watchdog"), dict) else {}
    if not bool(watchdog.get("enabled", True)):
        return {
            "status": "IDLE",
            "error_code": "WATCHDOG_DISABLED",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
        }

    heartbeat_path = _lock_paths(workspace_root)[1]
    heartbeat = _load_heartbeat(heartbeat_path)
    if not isinstance(heartbeat, dict):
        return {
            "status": "IDLE",
            "error_code": "HEARTBEAT_MISSING",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
        }
    last_tick_at = _parse_iso(str(heartbeat.get("last_tick_at") or ""))
    if not last_tick_at:
        return {
            "status": "IDLE",
            "error_code": "HEARTBEAT_INVALID",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
        }

    stale_seconds = int(watchdog.get("heartbeat_stale_seconds", 0) or 0)
    now = datetime.now(timezone.utc)
    if stale_seconds and now - last_tick_at < timedelta(seconds=stale_seconds):
        return {
            "status": "IDLE",
            "error_code": "HEARTBEAT_FRESH",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
        }

    state = _load_watchdog_state(workspace_root)
    today = now.date().isoformat()
    recoveries = int(state.get("recoveries", 0) or 0)
    if str(state.get("date") or "") != today:
        recoveries = 0
    max_recoveries = int(watchdog.get("max_recoveries_per_day", 0) or 0)
    if max_recoveries and recoveries >= max_recoveries:
        return {
            "status": "IDLE",
            "error_code": "WATCHDOG_LIMIT_REACHED",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
        }

    tick_result = run_airunner_tick(workspace_root=workspace_root)
    recoveries += 1
    state = {
        "version": "v1",
        "date": today,
        "recoveries": recoveries,
        "last_recovery_at": _now_iso(),
        "policy_hash": policy_hash,
        "notes": notes + ["PROGRAM_LED=true"],
    }
    state_path = _write_watchdog_state(workspace_root, state)
    return {
        "status": tick_result.get("status") if isinstance(tick_result, dict) else "WARN",
        "error_code": tick_result.get("error_code"),
        "policy_source": policy_source,
        "policy_hash": policy_hash,
        "watchdog_state_path": state_path,
        "tick_report_path": tick_result.get("report_path") if isinstance(tick_result, dict) else "",
    }
