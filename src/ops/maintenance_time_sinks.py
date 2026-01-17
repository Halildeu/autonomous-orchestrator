from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def prune_time_sinks_report(
    *,
    workspace_root: Path,
    max_age_seconds: int,
    dry_run: bool,
) -> dict[str, Any]:
    report_rel = str(Path(".cache") / "reports" / "time_sinks.v1.json")
    md_rel = str(Path(".cache") / "reports" / "time_sinks.v1.md")
    report_path = workspace_root / report_rel
    md_path = workspace_root / md_rel

    if max_age_seconds < 0:
        return {
            "status": "FAIL",
            "error": "INVALID_MAX_AGE_SECONDS",
            "report_path": report_rel,
            "dry_run": bool(dry_run),
        }

    if not report_path.exists():
        return {
            "status": "IDLE",
            "reason": "report_missing",
            "report_path": report_rel,
            "dry_run": bool(dry_run),
        }

    try:
        obj = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "status": "FAIL",
            "error": "INVALID_REPORT_JSON",
            "report_path": report_rel,
            "dry_run": bool(dry_run),
        }

    sinks = obj.get("sinks") if isinstance(obj, dict) else None
    if not isinstance(sinks, list):
        return {
            "status": "FAIL",
            "error": "INVALID_SINKS_LIST",
            "report_path": report_rel,
            "dry_run": bool(dry_run),
        }

    now = datetime.now(timezone.utc)
    kept: list[dict[str, Any]] = []
    pruned: list[dict[str, Any]] = []
    for sink in sinks:
        if not isinstance(sink, dict):
            continue
        last_seen = _parse_iso(str(sink.get("last_seen") or ""))
        if not last_seen:
            pruned.append(sink)
            continue
        age_seconds = int((now - last_seen).total_seconds())
        if age_seconds > max_age_seconds:
            pruned.append(sink)
        else:
            kept.append(sink)

    kept.sort(key=lambda s: (str(s.get("event_key") or ""), str(s.get("op_name") or "")))
    status = "OK" if kept else "IDLE"
    result = {
        "status": "WOULD_WRITE" if dry_run else "OK",
        "report_path": report_rel,
        "md_path": md_rel,
        "max_age_seconds": int(max_age_seconds),
        "cutoff_at": _now_iso(),
        "sinks_total": len(sinks),
        "sinks_kept": len(kept),
        "sinks_pruned": len(pruned),
        "dry_run": bool(dry_run),
    }

    if dry_run:
        return result

    payload = obj if isinstance(obj, dict) else {}
    payload["generated_at"] = _now_iso()
    payload["status"] = status
    payload["sinks"] = kept
    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    notes = [str(n) for n in notes if isinstance(n, str)]
    if pruned:
        notes.append(f"pruned_stale_sinks={len(pruned)}")
    payload["notes"] = sorted(set(notes))

    _atomic_write(report_path, _dump_json(payload))

    md_lines = [
        "# Time Sinks (v1)",
        "",
        f"Status: {status}",
        f"Pruned stale sinks: {len(pruned)}",
        f"Max age seconds: {max_age_seconds}",
        "",
        "Sinks:",
    ]
    for sink in kept[:5]:
        md_lines.append(
            f"- {sink.get('event_key')} p50_ms={sink.get('p50_ms')} p95_ms={sink.get('p95_ms')} "
            f"threshold_ms={sink.get('threshold_ms')} count={sink.get('count')} last_seen={sink.get('last_seen')}"
        )
    _atomic_write(md_path, "\n".join(md_lines) + "\n")

    result["status"] = status
    return result
