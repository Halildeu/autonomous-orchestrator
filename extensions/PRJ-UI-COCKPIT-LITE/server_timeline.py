from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server_utils import _parse_iso


TIMELINE_SUMMARY_REL = Path(".cache") / "reports" / "codex_timeline_summary.v1.json"
TIMELINE_WATCHDOG_REL = Path(".cache") / "ops" / "codex_timeline_watchdog.v1.py"


def _short_str(value: Any, limit: int = 300) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _pctl(values: list[int], p: float) -> int:
    nums = sorted(int(v) for v in values if isinstance(v, (int, float)))
    if not nums:
        return 0
    idx = max(0, min(len(nums) - 1, int(round((len(nums) - 1) * float(p)))))
    return int(nums[idx])


def _build_timeline_process_windows(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    now_dt = datetime.now(timezone.utc)
    current: dict[str, Any] | None = None
    current_start_dt: datetime | None = None

    def _close_current(end_dt: datetime, end_ts: str, closed_by: str) -> None:
        nonlocal current, current_start_dt
        if not current or current_start_dt is None:
            current = None
            current_start_dt = None
            return
        total_ms = max(0, int((end_dt - current_start_dt).total_seconds() * 1000))
        tool_total_ms = int(current.get("tool_total_ms") or 0)
        first_tool_start_dt = current.get("first_tool_start_dt")
        last_tool_end_dt = current.get("last_tool_end_dt")
        wait_first_tool_ms = (
            max(0, int((first_tool_start_dt - current_start_dt).total_seconds() * 1000))
            if isinstance(first_tool_start_dt, datetime)
            else None
        )
        last_tool_to_answer_ms = (
            max(0, int((end_dt - last_tool_end_dt).total_seconds() * 1000))
            if isinstance(last_tool_end_dt, datetime)
            else None
        )
        tool_breakdown = current.get("tool_breakdown") if isinstance(current.get("tool_breakdown"), dict) else {}
        top_tool = ""
        if tool_breakdown:
            top_tool = max(tool_breakdown.items(), key=lambda item: int(item[1]))[0]
        windows.append(
            {
                "started_at": str(current.get("started_at") or ""),
                "ended_at": end_ts,
                "closed_by": closed_by,
                "user_hint": str(current.get("user_hint") or ""),
                "duration_ms": total_ms,
                "tool_total_ms": tool_total_ms,
                "non_tool_ms": max(0, total_ms - tool_total_ms),
                "wait_first_tool_ms": wait_first_tool_ms,
                "last_tool_to_answer_ms": last_tool_to_answer_ms,
                "tool_calls": int(current.get("tool_calls") or 0),
                "slow_tool_calls": int(current.get("slow_tool_calls") or 0),
                "top_tool": top_tool,
                "tool_breakdown": {str(k): int(v) for k, v in tool_breakdown.items()},
            }
        )
        current = None
        current_start_dt = None

    for event in timeline:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("kind") or "")
        ts = str(event.get("ts") or "")
        dt = _parse_iso(ts)
        if dt is None:
            continue
        if kind == "user_message":
            if current and current_start_dt is not None:
                _close_current(dt, ts, "next_user")
            current_start_dt = dt
            current = {
                "started_at": ts,
                "user_hint": _short_str(event.get("detail") or "", 140),
                "tool_calls": 0,
                "slow_tool_calls": 0,
                "tool_total_ms": 0,
                "tool_breakdown": {},
                "first_tool_start_dt": None,
                "last_tool_end_dt": None,
            }
            continue
        if not current or current_start_dt is None:
            continue
        if kind == "tool_call_start":
            if current.get("first_tool_start_dt") is None:
                current["first_tool_start_dt"] = dt
            continue
        if kind == "tool_call_end":
            tool_name = str(event.get("tool") or "tool")
            duration_ms = max(0, _safe_int(event.get("duration_ms"), 0))
            current["tool_calls"] = int(current.get("tool_calls") or 0) + 1
            current["tool_total_ms"] = int(current.get("tool_total_ms") or 0) + duration_ms
            breakdown = current.get("tool_breakdown")
            if not isinstance(breakdown, dict):
                breakdown = {}
            breakdown[tool_name] = int(breakdown.get(tool_name) or 0) + duration_ms
            current["tool_breakdown"] = breakdown
            current["last_tool_end_dt"] = dt
            if duration_ms >= 15_000:
                current["slow_tool_calls"] = int(current.get("slow_tool_calls") or 0) + 1
            continue
        if kind == "assistant_message":
            _close_current(dt, ts, "assistant")

    if current and current_start_dt is not None:
        _close_current(now_dt, now_dt.isoformat().replace("+00:00", "Z"), "open")
    return windows


def derive_timeline_dashboard(report: dict[str, Any]) -> dict[str, Any]:
    detail = report.get("detail") if isinstance(report.get("detail"), dict) else {}
    stats = detail.get("stats") if isinstance(detail.get("stats"), dict) else {}
    selected_rollout = detail.get("selected_rollout") if isinstance(detail.get("selected_rollout"), dict) else {}
    tool_summary = detail.get("tool_call_summary") if isinstance(detail.get("tool_call_summary"), dict) else {}
    completed_by_tool = tool_summary.get("completed_by_tool") if isinstance(tool_summary.get("completed_by_tool"), list) else []
    completed_by_tool = [row for row in completed_by_tool if isinstance(row, dict)]
    completed_by_tool.sort(key=lambda row: int(row.get("total_ms") or 0), reverse=True)

    timeline = detail.get("timeline") if isinstance(detail.get("timeline"), list) else []
    timeline_events = [event for event in timeline if isinstance(event, dict)]
    windows = _build_timeline_process_windows(timeline_events)
    windows.sort(key=lambda row: int(row.get("duration_ms") or 0), reverse=True)

    durations = [int(row.get("duration_ms") or 0) for row in windows]
    tool_totals = [int(row.get("tool_total_ms") or 0) for row in windows]
    non_tool_totals = [int(row.get("non_tool_ms") or 0) for row in windows]

    total_ms = int(tool_summary.get("completed_total_ms") or 0)
    if total_ms <= 0:
        total_ms = sum(tool_totals)

    cycle_summary = {
        "count": len(windows),
        "avg_ms": int(sum(durations) / max(1, len(durations))) if durations else 0,
        "p95_ms": _pctl(durations, 0.95),
        "max_ms": max(durations) if durations else 0,
        "tool_total_ms": int(sum(tool_totals)),
        "non_tool_total_ms": int(sum(non_tool_totals)),
        "non_tool_ratio": round((sum(non_tool_totals) / max(1, sum(durations))), 3) if durations else 0,
    }

    hottest_non_tool = max(windows, key=lambda row: int(row.get("non_tool_ms") or 0), default=None)
    hottest_total = max(windows, key=lambda row: int(row.get("duration_ms") or 0), default=None)
    hotspots: list[dict[str, Any]] = []
    if isinstance(hottest_non_tool, dict):
        hotspots.append(
            {
                "kind": "non_tool_overhead",
                "user_hint": str(hottest_non_tool.get("user_hint") or ""),
                "duration_ms": int(hottest_non_tool.get("non_tool_ms") or 0),
            }
        )
    if isinstance(hottest_total, dict):
        hotspots.append(
            {
                "kind": "slowest_cycle",
                "user_hint": str(hottest_total.get("user_hint") or ""),
                "duration_ms": int(hottest_total.get("duration_ms") or 0),
                "top_tool": str(hottest_total.get("top_tool") or ""),
            }
        )

    return {
        "generated_at": str(report.get("generated_at") or ""),
        "selected_rollout": {
            "path": str(selected_rollout.get("path") or ""),
            "size_human": str(selected_rollout.get("size_human") or ""),
            "mtime": str(selected_rollout.get("mtime") or ""),
        },
        "stats": {
            "events_in_window": _safe_int(stats.get("events_in_window"), 0),
            "tool_calls_completed": _safe_int(stats.get("tool_calls_completed"), 0),
            "tool_calls_pending": _safe_int(stats.get("tool_calls_pending"), 0),
            "slow_calls_count": _safe_int(stats.get("slow_calls_count"), 0),
            "stuck_calls_count": _safe_int(stats.get("stuck_calls_count"), 0),
        },
        "tool_summary": {
            "completed_total_ms": int(total_ms),
            "completed_by_tool": completed_by_tool[:12],
        },
        "cycle_summary": cycle_summary,
        "slow_cycles": windows[:10],
        "recent_cycles": sorted(windows, key=lambda row: str(row.get("started_at") or ""), reverse=True)[:10],
        "hotspots": hotspots[:8],
    }


def run_timeline_watchdog(repo_root: Path, ws_root: Path) -> dict[str, Any]:
    script_path = ws_root / TIMELINE_WATCHDOG_REL
    out_path = ws_root / TIMELINE_SUMMARY_REL
    if not script_path.exists():
        return {
            "status": "FAIL",
            "error": "TIMELINE_SCRIPT_NOT_FOUND",
            "script_path": str(script_path),
            "out_path": str(out_path),
        }
    cmd = [
        sys.executable,
        str(script_path),
        "--ws",
        str(ws_root),
        "--out",
        str(out_path),
        "--top",
        "0",
        "--tail-bytes",
        "12000000",
        "--tail-lines",
        "15000",
        "--max-events",
        "1200",
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=60)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "OK" if proc.returncode == 0 else "FAIL",
            "returncode": int(proc.returncode),
            "elapsed_ms": elapsed_ms,
            "cmd": cmd,
            "script_path": str(script_path),
            "out_path": str(out_path),
            "stdout_tail": _short_str(proc.stdout or "", 2000),
            "stderr_tail": _short_str(proc.stderr or "", 2000),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "FAIL",
            "error": "TIMELINE_RUN_TIMEOUT",
            "elapsed_ms": elapsed_ms,
            "cmd": cmd,
            "script_path": str(script_path),
            "out_path": str(out_path),
            "stdout_tail": _short_str((exc.stdout or ""), 1200),
            "stderr_tail": _short_str((exc.stderr or ""), 1200),
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "status": "FAIL",
            "error": "TIMELINE_RUN_EXCEPTION",
            "elapsed_ms": elapsed_ms,
            "cmd": cmd,
            "script_path": str(script_path),
            "out_path": str(out_path),
            "detail": _short_str(exc, 500),
        }
