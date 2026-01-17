from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _perf_events_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "airunner" / "perf_events.v1.jsonl"


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "version": "v1",
        "event_type": str(event.get("event_type") or "OP_CALL"),
        "op_name": str(event.get("op_name") or ""),
        "started_at": str(event.get("started_at") or _now_iso()),
        "ended_at": str(event.get("ended_at") or _now_iso()),
        "duration_ms": int(event.get("duration_ms") or 0),
        "status": str(event.get("status") or "OK"),
        "notes": [str(n) for n in event.get("notes", []) if isinstance(n, str)],
    }
    if isinstance(event.get("job_id"), str):
        payload["job_id"] = event["job_id"]
    payload["event_id"] = _hash_text(_canonical_json(payload))
    return payload


def append_perf_event(
    workspace_root: Path,
    *,
    event: dict[str, Any],
    max_lines: int,
) -> str:
    path = _perf_events_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    max_lines = max(0, int(max_lines))
    sanitized = _sanitize_event(event)
    lines: list[str] = []
    if path.exists():
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines.append(json.dumps(sanitized, ensure_ascii=False, sort_keys=True))
    if max_lines and len(lines) > max_lines:
        lines = lines[-max_lines:]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(Path(".cache") / "airunner" / "perf_events.v1.jsonl")


def load_perf_events(workspace_root: Path, *, max_lines: int) -> list[dict[str, Any]]:
    path = _perf_events_path(workspace_root)
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    if max_lines and len(lines) > max_lines:
        lines = lines[-max_lines:]
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events
