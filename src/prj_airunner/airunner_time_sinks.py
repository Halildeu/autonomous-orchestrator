from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.prj_airunner.airunner_perf import load_perf_events


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, int(math.ceil(pct * len(ordered))) - 1)
    return int(ordered[min(idx, len(ordered) - 1)])


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _thresholds_for(policy: dict[str, Any]) -> dict[str, int]:
    thresholds = policy.get("perf", {}).get("thresholds_ms") if isinstance(policy.get("perf"), dict) else {}
    if not isinstance(thresholds, dict):
        thresholds = {}
    return {
        "SMOKE_FULL": int(thresholds.get("smoke_full_p95_warn", 0) or 0),
        "SMOKE_FAST": int(thresholds.get("smoke_fast_p95_warn", 0) or 0),
        "RELEASE_PREPARE": int(thresholds.get("release_prepare_p95_warn", 0) or 0),
    }


def build_time_sinks_report(workspace_root: Path, *, policy: dict[str, Any]) -> dict[str, Any]:
    perf_cfg = policy.get("perf") if isinstance(policy.get("perf"), dict) else {}
    window = int(perf_cfg.get("time_sinks_window", 0) or 0)
    max_lines = int(perf_cfg.get("event_log_max_lines", 0) or 0)
    events = load_perf_events(workspace_root, max_lines=max_lines)
    if window and len(events) > window:
        events = events[-window:]

    thresholds = _thresholds_for(policy)
    durations_by_key: dict[str, list[int]] = {}
    last_seen_by_key: dict[str, datetime] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        key = str(ev.get("op_name") or "")
        if key not in thresholds:
            continue
        dur = ev.get("duration_ms")
        if not isinstance(dur, int):
            continue
        durations_by_key.setdefault(key, []).append(dur)
        ended_at = _parse_iso(str(ev.get("ended_at") or ""))
        if ended_at:
            current = last_seen_by_key.get(key)
            if current is None or ended_at > current:
                last_seen_by_key[key] = ended_at

    sinks: list[dict[str, Any]] = []
    for key in sorted(durations_by_key):
        threshold = thresholds.get(key, 0)
        if threshold <= 0:
            continue
        values = durations_by_key.get(key, [])
        if not values:
            continue
        p50 = _percentile(values, 0.50)
        p95 = _percentile(values, 0.95)
        breach_count = len([v for v in values if v >= threshold])
        status = "WARN" if p95 >= threshold else "OK"
        if status != "WARN":
            continue
        last_seen = last_seen_by_key.get(key)
        sinks.append(
            {
                "op_name": key,
                "event_key": key,
                "count": int(len(values)),
                "p50_ms": int(p50),
                "p95_ms": int(p95),
                "threshold_ms": int(threshold),
                "breach_count": int(breach_count),
                "last_seen": last_seen.replace(microsecond=0).isoformat().replace("+00:00", "Z") if last_seen else "",
                "status": status,
            }
        )

    status = "OK" if sinks else "IDLE"
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "window_size": len(events),
        "thresholds_ms": {
            "smoke_full_p95_warn": int(thresholds.get("SMOKE_FULL", 0)),
            "smoke_fast_p95_warn": int(thresholds.get("SMOKE_FAST", 0)),
            "release_prepare_p95_warn": int(thresholds.get("RELEASE_PREPARE", 0)),
        },
        "sinks": sinks,
        "notes": [],
    }
    out_json = workspace_root / ".cache" / "reports" / "time_sinks.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "time_sinks.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(payload), encoding="utf-8")

    md_lines = [
        "# Time Sinks (v1)",
        "",
        f"Status: {status}",
        f"Window size: {len(events)}",
        "",
        "Sinks:",
    ]
    for sink in sinks[:5]:
        md_lines.append(
            f"- {sink.get('event_key')} p50_ms={sink.get('p50_ms')} p95_ms={sink.get('p95_ms')} threshold_ms={sink.get('threshold_ms')} count={sink.get('count')} last_seen={sink.get('last_seen')}"
        )
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return payload
