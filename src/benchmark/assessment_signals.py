from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _load_pdca_cursor_signal(*, workspace_root: Path) -> dict[str, Any]:
    cursor_path = workspace_root / ".cache" / "index" / "pdca_cursor.v1.json"
    if not cursor_path.exists():
        return {"stale_hours": 0.0, "cursor_hash": "", "last_updated": ""}
    try:
        obj = _load_json(cursor_path)
    except Exception:
        return {"stale_hours": 0.0, "cursor_hash": "", "last_updated": ""}
    last_run_at = obj.get("last_run_at") if isinstance(obj, dict) else None
    last_dt = _parse_iso(last_run_at) if isinstance(last_run_at, str) else None
    stale_hours = 0.0
    if last_dt is not None:
        stale_hours = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0)
    cursor_hash = ""
    if isinstance(obj, dict):
        hashes = obj.get("hashes")
        if isinstance(hashes, dict):
            cursor_hash = str(hashes.get("gap_register") or "")
    return {
        "stale_hours": round(float(stale_hours), 4),
        "cursor_hash": cursor_hash,
        "last_updated": str(last_run_at or ""),
    }


def _load_integration_coherence_signals(*, workspace_root: Path) -> dict[str, Any]:
    layer_boundary_count = 0
    layer_path = workspace_root / ".cache" / "reports" / "layer_boundary_report.v1.json"
    if layer_path.exists():
        try:
            obj = _load_json(layer_path)
            would_block = obj.get("would_block") if isinstance(obj, dict) else None
            layer_boundary_count = len(would_block) if isinstance(would_block, list) else 0
        except Exception:
            layer_boundary_count = 0

    pack_conflicts = 0
    pack_path = workspace_root / ".cache" / "index" / "pack_validation_report.json"
    if pack_path.exists():
        try:
            obj = _load_json(pack_path)
            hard_conflicts = obj.get("hard_conflicts") if isinstance(obj, dict) else None
            soft_conflicts = obj.get("soft_conflicts") if isinstance(obj, dict) else None
            pack_conflicts = (len(hard_conflicts) if isinstance(hard_conflicts, list) else 0) + (
                len(soft_conflicts) if isinstance(soft_conflicts, list) else 0
            )
        except Exception:
            pack_conflicts = 0

    core_unlock_scope_widen = 1 if (
        workspace_root / ".cache" / "reports" / "core_unlock_compliance.v1.json"
    ).exists() else 0

    schema_fail_count = 0
    preflight_path = workspace_root / ".cache" / "reports" / "preflight_stamp.v1.json"
    if preflight_path.exists():
        try:
            obj = _load_json(preflight_path)
            gates = obj.get("gates") if isinstance(obj, dict) else None
            validate_status = gates.get("validate_schemas") if isinstance(gates, dict) else None
            if isinstance(validate_status, str) and validate_status != "PASS":
                schema_fail_count = 1
        except Exception:
            schema_fail_count = 0

    return {
        "layer_boundary_violations_count": int(layer_boundary_count),
        "pack_conflict_count": int(pack_conflicts),
        "core_unlock_scope_widen_count": int(core_unlock_scope_widen),
        "schema_fail_count": int(schema_fail_count),
    }
