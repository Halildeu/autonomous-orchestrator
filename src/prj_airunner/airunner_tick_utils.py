from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from src.prj_airunner.airunner_perf import append_perf_event

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback for older runtimes
    ZoneInfo = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _active_hours_snapshot(schedule: dict[str, Any], now: datetime) -> dict[str, Any]:
    notes: list[str] = []
    active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
    active_hours_enabled = bool(active_hours.get("enabled", False))
    tz_name = str(active_hours.get("tz") or "UTC")
    if ZoneInfo is not None:
        try:
            now_local = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            now_local = now
            notes.append("active_hours_tz_invalid")
    else:
        now_local = now
        notes.append("active_hours_tz_missing")
    now_local_hhmm = f"{now_local.hour:02d}:{now_local.minute:02d}"
    inside, inside_notes = _within_active_hours(schedule, now)
    outside_hours_mode = str(schedule.get("outside_hours_mode") or "poll_only")
    if not active_hours_enabled:
        outside_hours_mode_effective = "ignore"
    elif outside_hours_mode in {"ignore", "poll_only", "idle"}:
        outside_hours_mode_effective = outside_hours_mode
    else:
        outside_hours_mode_effective = "poll_only"
        notes.append("outside_hours_mode_invalid")
    notes = sorted(set(notes + inside_notes))
    return {
        "active_hours_enabled": active_hours_enabled,
        "active_hours_tz": tz_name,
        "now_local_hhmm": now_local_hhmm,
        "inside_active_hours": bool(inside),
        "outside_hours_mode_effective": outside_hours_mode_effective,
        "notes": notes,
    }

def _within_active_hours(schedule: dict[str, Any], now: datetime) -> tuple[bool, list[str]]:
    notes: list[str] = []
    active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
    active_hours_enabled = bool(active_hours.get("enabled", False))
    weekday_only = bool(schedule.get("weekday_only", False))
    if not active_hours_enabled:
        notes.append("active_hours_disabled")
        return True, notes
    if not active_hours:
        return True, notes
    tz_name = str(active_hours.get("tz") or "UTC")
    start_raw = str(active_hours.get("start") or "")
    end_raw = str(active_hours.get("end") or "")
    start = _parse_hhmm(start_raw)
    end = _parse_hhmm(end_raw)
    if not start or not end:
        notes.append("active_hours_invalid")
        return True, notes
    if ZoneInfo is not None:
        try:
            now_local = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            now_local = now
            notes.append("active_hours_tz_invalid")
    else:
        now_local = now
        notes.append("active_hours_tz_missing")
    if weekday_only and now_local.weekday() >= 5:
        return False, notes
    start_minutes = start[0] * 60 + start[1]
    end_minutes = end[0] * 60 + end[1]
    now_minutes = now_local.hour * 60 + now_local.minute
    if start_minutes == end_minutes:
        return True, notes
    if start_minutes < end_minutes:
        return start_minutes <= now_minutes < end_minutes, notes
    return now_minutes >= start_minutes or now_minutes < end_minutes, notes

def _runtime_state_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "airunner" / "airunner_runtime.v1.json"


def _runtime_day(schedule: dict[str, Any], now: datetime) -> tuple[str, list[str]]:
    notes: list[str] = []
    active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
    active_hours_enabled = bool(active_hours.get("enabled", False))
    tz_name = str(active_hours.get("tz") or "UTC")
    if ZoneInfo is not None:
        try:
            now_local = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            now_local = now
            notes.append("runtime_tz_invalid")
    else:
        now_local = now
        notes.append("runtime_tz_missing")
    return now_local.date().isoformat(), notes


def _load_runtime_state(workspace_root: Path) -> dict[str, Any]:
    path = _runtime_state_path(workspace_root)
    if not path.exists():
        return {}
    try:
        obj = _load_json(path)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_runtime_state(
    workspace_root: Path, *, runtime_day: str, runtime_seconds: int, now: datetime, notes: list[str]
) -> str:
    payload = {
        "version": "v1",
        "date": runtime_day,
        "runtime_seconds": int(max(0, runtime_seconds)),
        "last_tick_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "notes": notes,
    }
    path = _runtime_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(payload), encoding="utf-8")
    return _rel_to_workspace(path, workspace_root) or str(path)


def _lock_paths(workspace_root: Path) -> tuple[Path, Path]:
    base = workspace_root / ".cache" / "airunner"
    return base / "airunner_lock.v1.json", base / "airunner_heartbeat.v1.json"


def _load_lock(lock_path: Path) -> dict[str, Any] | None:
    if not lock_path.exists():
        return None
    try:
        obj = _load_json(lock_path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _lock_is_stale(lock: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(lock.get("expires_at") if isinstance(lock, dict) else None)
    if expires_at is None:
        return True
    return now >= expires_at


def _write_lock(lock_path: Path, *, lock_id: str, now: datetime, ttl_seconds: int, workspace_root: Path) -> None:
    expires_at = now + timedelta(seconds=int(ttl_seconds))
    payload = {
        "version": "v1",
        "lock_id": lock_id,
        "acquired_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": int(ttl_seconds),
        "workspace_root": str(workspace_root),
        "notes": ["PROGRAM_LED=true"],
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(_dump_json(payload), encoding="utf-8")


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def _load_heartbeat(heartbeat_path: Path) -> dict[str, Any] | None:
    if not heartbeat_path.exists():
        return None
    try:
        obj = _load_json(heartbeat_path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_heartbeat(
    heartbeat_path: Path,
    *,
    workspace_root: Path,
    tick_id: str,
    status: str,
    error_code: str | None,
    window_bucket: str,
    policy_hash: str,
    notes: list[str],
) -> str:
    now = _now_iso()
    payload = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(workspace_root),
        "last_tick_id": tick_id,
        "last_tick_at": now,
        "ended_at": now,
        "last_status": status,
        "last_error_code": error_code,
        "last_tick_window": window_bucket,
        "policy_hash": policy_hash,
        "notes": notes,
    }
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path.write_text(_dump_json(payload), encoding="utf-8")
    return _rel_to_workspace(heartbeat_path, workspace_root) or str(heartbeat_path)


def _heartbeat_age_seconds(heartbeat: dict[str, Any] | None, now: datetime) -> int | None:
    if not isinstance(heartbeat, dict):
        return None
    last_tick_at = _parse_iso(str(heartbeat.get("last_tick_at") or ""))
    if last_tick_at is None:
        return None
    return int((now - last_tick_at).total_seconds())


def _run_cmd_json(func, args: argparse.Namespace) -> dict[str, Any]:
    buf = StringIO()
    try:
        from contextlib import redirect_stdout, redirect_stderr

        with redirect_stdout(buf), redirect_stderr(buf):
            rc = func(args)
    except Exception:
        return {"status": "FAIL", "error_code": "COMMAND_EXCEPTION"}

    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    if not lines:
        return {"status": "WARN", "error_code": "COMMAND_NO_OUTPUT", "return_code": rc}
    try:
        payload = json.loads(lines[-1])
    except Exception:
        return {"status": "WARN", "error_code": "COMMAND_OUTPUT_INVALID", "return_code": rc}
    if isinstance(payload, dict):
        payload["return_code"] = rc
    return payload if isinstance(payload, dict) else {"status": "WARN", "return_code": rc}


def _perf_status(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "WARN")
    if payload.get("return_code") not in {None, 0}:
        return "FAIL"
    if status in {"OK"}:
        return "OK"
    if status in {"WARN", "IDLE"}:
        return "WARN"
    return "FAIL"


def _run_cmd_json_with_perf(
    *,
    op_name: str,
    func,
    args: argparse.Namespace,
    workspace_root: Path,
    perf_cfg: dict[str, Any],
) -> dict[str, Any]:
    started_at = _now_iso()
    start = time.monotonic()
    payload = _run_cmd_json(func, args)
    duration_ms = int((time.monotonic() - start) * 1000)
    ended_at = _now_iso()
    if perf_cfg.get("enable", True):
        max_lines = int(perf_cfg.get("event_log_max_lines", 0) or 0)
        append_perf_event(
            workspace_root,
            event={
                "event_type": "OP_CALL",
                "op_name": op_name,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "status": _perf_status(payload),
                "notes": ["PROGRAM_LED=true"],
            },
            max_lines=max_lines,
        )
    return payload
