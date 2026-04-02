from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _lease_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "file_write_leases.v1.json"


def _load_leases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    leases = raw.get("leases") if isinstance(raw, dict) else raw
    if not isinstance(leases, list):
        return []
    return [item for item in leases if isinstance(item, dict)]


def _save_leases(path: Path, leases: list[dict[str, Any]]) -> None:
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "leases": sorted(
            leases,
            key=lambda item: (
                str(item.get("target_path") or ""),
                str(item.get("run_id") or ""),
            ),
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _is_stale(lease: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(str(lease.get("expires_at") or ""))
    if expires_at is None:
        return True
    return now >= expires_at


def acquire_path_write_lease(
    *,
    workspace_root: Path,
    target_path: Path,
    run_id: str,
    owner_tag: str,
    owner_session: str,
    evidence_paths: list[str] | None,
    ttl_seconds: int = 120,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    path = _lease_path(workspace_root)
    leases = _load_leases(path)
    target_str = str(target_path.resolve())
    stale_cleared: dict[str, Any] | None = None

    for idx, lease in enumerate(list(leases)):
        if str(lease.get("target_path") or "") != target_str:
            continue
        if _is_stale(lease, now):
            stale_cleared = dict(lease)
            leases.pop(idx)
            break
        if str(lease.get("run_id") or "") == str(run_id or ""):
            updated = dict(lease)
            updated["heartbeat_at"] = _now_iso()
            updated["expires_at"] = (now + timedelta(seconds=max(1, int(ttl_seconds)))).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            updated["evidence_paths"] = sorted(
                set(str(x).strip() for x in (evidence_paths or []) if isinstance(x, str) and str(x).strip())
            )
            leases[idx] = updated
            _save_leases(path, leases)
            return {"status": "RENEWED", "lease": updated, "stale_cleared": stale_cleared}
        return {"status": "LOCKED", "lease": lease, "stale_cleared": None}

    lease = {
        "target_path": target_str,
        "run_id": str(run_id or ""),
        "owner_tag": str(owner_tag or ""),
        "owner_session": str(owner_session or ""),
        "acquired_at": _now_iso(),
        "heartbeat_at": _now_iso(),
        "ttl_seconds": max(1, int(ttl_seconds)),
        "expires_at": (now + timedelta(seconds=max(1, int(ttl_seconds)))).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "evidence_paths": sorted(
            set(str(x).strip() for x in (evidence_paths or []) if isinstance(x, str) and str(x).strip())
        ),
    }
    leases.append(lease)
    _save_leases(path, leases)
    return {"status": "ACQUIRED", "lease": lease, "stale_cleared": stale_cleared}


def release_path_write_lease(*, workspace_root: Path, target_path: Path, run_id: str) -> dict[str, Any]:
    path = _lease_path(workspace_root)
    leases = _load_leases(path)
    target_str = str(target_path.resolve())
    for idx, lease in enumerate(list(leases)):
        if str(lease.get("target_path") or "") != target_str:
            continue
        if str(lease.get("run_id") or "") != str(run_id or ""):
            return {"status": "MISMATCH", "lease": lease}
        leases.pop(idx)
        _save_leases(path, leases)
        return {"status": "RELEASED", "lease": lease}
    return {"status": "NOOP", "lease": None}


def summarize_path_write_leases(*, workspace_root: Path) -> dict[str, Any]:
    path = _lease_path(workspace_root)
    leases = _load_leases(path)
    now = datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    stale_count = 0
    for lease in leases:
        if _is_stale(lease, now):
            stale_count += 1
            continue
        active.append(lease)
    active_targets = sorted(
        set(str(item.get("target_path") or "").strip() for item in active if str(item.get("target_path") or "").strip())
    )
    latest_heartbeat = ""
    for item in active:
        heartbeat = str(item.get("heartbeat_at") or "").strip()
        if heartbeat and heartbeat > latest_heartbeat:
            latest_heartbeat = heartbeat
    return {
        "lease_path": str(path),
        "active_lease_count": len(active),
        "stale_lease_count": stale_count,
        "active_targets": active_targets[:10],
        "latest_heartbeat_at": latest_heartbeat,
    }
