from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
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
    return workspace_root / ".cache" / "index" / "work_item_leases.v1.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _lease_is_stale(lease: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(str(lease.get("expires_at") or ""))
    if expires_at is None:
        return True
    return now >= expires_at


def _normalize_leases(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        leases = raw.get("leases")
    else:
        leases = raw
    if not isinstance(leases, list):
        return []
    return [item for item in leases if isinstance(item, dict)]


def load_leases(workspace_root: Path) -> list[dict[str, Any]]:
    path = _lease_path(workspace_root)
    if not path.exists():
        return []
    try:
        raw = _load_json(path)
    except Exception:
        return []
    return _normalize_leases(raw)


def save_leases(workspace_root: Path, leases: list[dict[str, Any]]) -> None:
    leases_sorted = sorted(leases, key=lambda l: (str(l.get("work_item_id") or ""), str(l.get("lease_id") or "")))
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "leases": leases_sorted,
    }
    _write_json(_lease_path(workspace_root), payload)


def acquire_lease(
    *,
    workspace_root: Path,
    work_item_id: str,
    run_id: str,
    owner: str,
    ttl_seconds: int,
) -> dict[str, Any]:
    ttl = max(1, int(ttl_seconds))
    now = datetime.now(timezone.utc)
    leases = load_leases(workspace_root)
    stale_cleared: dict[str, Any] | None = None

    for idx, lease in enumerate(list(leases)):
        if str(lease.get("work_item_id") or "") != work_item_id:
            continue
        if _lease_is_stale(lease, now):
            stale_cleared = dict(lease)
            leases.pop(idx)
            break
        return {"status": "LOCKED", "lease": lease, "stale_cleared": None}

    lease_id = sha256(f"{work_item_id}:{run_id}".encode("utf-8")).hexdigest()
    lease = {
        "work_item_id": work_item_id,
        "lease_id": lease_id,
        "owner": str(owner or ""),
        "run_id": run_id,
        "acquired_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": ttl,
        "expires_at": (now + timedelta(seconds=ttl)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "heartbeat_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    leases.append(lease)
    save_leases(workspace_root, leases)
    return {"status": "ACQUIRED", "lease": lease, "stale_cleared": stale_cleared}


def release_lease(
    *,
    workspace_root: Path,
    work_item_id: str,
    run_id: str | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    leases = load_leases(workspace_root)
    for idx, lease in enumerate(list(leases)):
        if str(lease.get("work_item_id") or "") != str(work_item_id or ""):
            continue
        if run_id and str(lease.get("run_id") or "") != str(run_id or ""):
            return {"status": "MISMATCH", "lease": lease}
        if owner and str(lease.get("owner") or "") != str(owner or ""):
            return {"status": "MISMATCH", "lease": lease}
        leases.pop(idx)
        save_leases(workspace_root, leases)
        return {"status": "RELEASED", "lease": lease}
    return {"status": "NOOP", "lease": None}


def count_active_leases(workspace_root: Path) -> int:
    now = datetime.now(timezone.utc)
    leases = load_leases(workspace_root)
    return sum(1 for lease in leases if isinstance(lease, dict) and not _lease_is_stale(lease, now))
