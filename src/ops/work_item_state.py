from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_OPEN = "OPEN"
STATE_PLANNED = "PLANNED"
STATE_IN_PROGRESS = "IN_PROGRESS"
STATE_APPLIED = "APPLIED"
STATE_CLOSED = "CLOSED"
STATE_NOOP = "NOOP"

FINAL_STATES = {STATE_APPLIED, STATE_CLOSED, STATE_NOOP}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _state_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "work_item_state.v1.json"


def _runs_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "work_item_runs.v1.jsonl"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _normalize_items(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        items = raw.get("items")
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    state_map: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        work_item_id = str(item.get("work_item_id") or "")
        if not work_item_id:
            continue
        state_map[work_item_id] = dict(item)
    return state_map


def load_state_map(workspace_root: Path) -> dict[str, dict[str, Any]]:
    path = _state_path(workspace_root)
    if not path.exists():
        return {}
    try:
        raw = _load_json(path)
    except Exception:
        return {}
    return _normalize_items(raw)


def save_state_map(workspace_root: Path, state_map: dict[str, dict[str, Any]]) -> None:
    items = sorted(state_map.values(), key=lambda x: str(x.get("work_item_id") or ""))
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": items,
    }
    _write_json(_state_path(workspace_root), payload)


def get_state_entry(workspace_root: Path, work_item_id: str) -> dict[str, Any] | None:
    state_map = load_state_map(workspace_root)
    entry = state_map.get(str(work_item_id or ""))
    return dict(entry) if isinstance(entry, dict) else None


def should_skip_due_to_fingerprint(entry: dict[str, Any] | None, fingerprint: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("last_fingerprint") or "") != str(fingerprint or ""):
        return False
    state = str(entry.get("state") or "")
    return state in FINAL_STATES


def update_state(
    *,
    workspace_root: Path,
    work_item_id: str,
    state: str,
    run_id: str,
    fingerprint: str,
    evidence_paths: list[str] | None,
    note: str | None = None,
) -> dict[str, Any]:
    state_map = load_state_map(workspace_root)
    item_id = str(work_item_id or "")
    if not item_id:
        return {}
    entry = dict(state_map.get(item_id) or {})
    entry.update(
        {
            "work_item_id": item_id,
            "state": str(state or ""),
            "last_run_id": str(run_id or ""),
            "last_fingerprint": str(fingerprint or ""),
            "last_updated_at": _now_iso(),
        }
    )
    paths = sorted({str(p) for p in (evidence_paths or []) if str(p).strip()})
    if paths:
        entry["evidence_paths"] = paths
    if note:
        entry["note"] = str(note)
    state_map[item_id] = entry
    save_state_map(workspace_root, state_map)
    return entry


def record_run(
    *,
    workspace_root: Path,
    run_id: str,
    work_item_id: str,
    fingerprint: str,
    state: str,
    result: str,
    evidence_paths: list[str] | None,
) -> None:
    record = {
        "version": "v1",
        "recorded_at": _now_iso(),
        "run_id": str(run_id or ""),
        "work_item_id": str(work_item_id or ""),
        "fingerprint": str(fingerprint or ""),
        "state": str(state or ""),
        "result": str(result or ""),
        "evidence_paths": sorted({str(p) for p in (evidence_paths or []) if str(p).strip()}),
    }
    out_path = _runs_path(workspace_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
