from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _lock_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "doer" / "doer_loop_lock.v1.json"


def _clear_stale_report_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "doer_loop_lock_clear_stale.v1.json"


def _load_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _is_stale(lock: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(str(lock.get("expires_at") or ""))
    if expires_at is None:
        return True
    return now >= expires_at


def owner_tag_from_env() -> str:
    tag = os.environ.get("CODEX_CHAT_TAG")
    return str(tag).strip() if isinstance(tag, str) and tag.strip() else "unknown"


def owner_session_from_env() -> str:
    return owner_tag_from_env()


def load_loop_lock_ttl_seconds(*, core_root: Path, workspace_root: Path) -> int:
    ttl_seconds = 900
    core_path = core_root / "policies" / "policy_airunner.v1.json"
    if core_path.exists():
        try:
            obj = _load_json(core_path)
            if isinstance(obj, dict) and isinstance(obj.get("lock_ttl_seconds"), int):
                ttl_seconds = int(obj.get("lock_ttl_seconds") or ttl_seconds)
        except Exception:
            pass
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict) and isinstance(obj.get("lock_ttl_seconds"), int):
                ttl_seconds = int(obj.get("lock_ttl_seconds") or ttl_seconds)
        except Exception:
            pass
    return max(60, ttl_seconds)


def acquire_doer_loop_lock(
    *,
    workspace_root: Path,
    owner_tag: str,
    owner_session: str | None = None,
    run_id: str,
    ttl_seconds: int,
) -> dict[str, Any]:
    now = _now()
    lock_path = _lock_path(workspace_root)
    lock = _load_lock(lock_path)
    if lock and not _is_stale(lock, now):
        return {
            "status": "LOCKED",
            "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
            "owner_tag": str(lock.get("owner_tag") or ""),
            "owner_session": str(lock.get("owner_session") or ""),
            "expires_at": str(lock.get("expires_at") or ""),
            "run_id": str(lock.get("run_id") or ""),
        }

    if lock and _is_stale(lock, now):
        clear_report = {
            "version": "v1",
            "cleared_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "previous_lock": lock,
            "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
        }
        clear_path = _clear_stale_report_path(workspace_root)
        clear_path.parent.mkdir(parents=True, exist_ok=True)
        clear_path.write_text(_dump_json(clear_report), encoding="utf-8")
        try:
            lock_path.unlink()
        except Exception:
            pass

    lease_id = _hash_text(f"{workspace_root}:{owner_tag}:{run_id}")
    expires_at = now + timedelta(seconds=int(ttl_seconds))
    session = str(owner_session or owner_tag)
    payload = {
        "version": "v1",
        "lease_id": lease_id,
        "lock_id": lease_id,
        "owner_tag": owner_tag,
        "owner_session": session,
        "run_id": run_id,
        "acquired_at": _now_iso(),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "heartbeat_at": _now_iso(),
        "ttl_seconds": int(ttl_seconds),
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(_dump_json(payload), encoding="utf-8")
    return {
        "status": "OK",
        "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
        "owner_tag": owner_tag,
        "owner_session": session,
        "expires_at": payload["expires_at"],
        "run_id": run_id,
        "lease_id": lease_id,
    }


def touch_doer_loop_lock(*, workspace_root: Path, lease_id: str) -> dict[str, Any]:
    lock_path = _lock_path(workspace_root)
    lock = _load_lock(lock_path)
    if not lock:
        return {"status": "MISSING"}
    if str(lock.get("lease_id") or "") != str(lease_id or ""):
        return {"status": "MISMATCH"}
    lock["heartbeat_at"] = _now_iso()
    lock_path.write_text(_dump_json(lock), encoding="utf-8")
    return {"status": "OK", "heartbeat_at": lock.get("heartbeat_at")}


def release_doer_loop_lock(*, workspace_root: Path, lease_id: str) -> bool:
    lock_path = _lock_path(workspace_root)
    lock = _load_lock(lock_path)
    if not lock:
        return False
    if str(lock.get("lease_id") or "") != str(lease_id or ""):
        return False
    try:
        lock_path.unlink()
    except Exception:
        return False
    return True
