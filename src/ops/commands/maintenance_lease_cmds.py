from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool
from src.ops.trace_meta import build_run_id, date_bucket_from_iso
from src.ops.work_item_leases import acquire_lease


def cmd_work_item_lease_seed(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    intake_id = str(args.intake_id).strip() if args.intake_id else ""
    owner = str(args.owner or "planner-proof").strip() or "planner-proof"
    try:
        ttl_seconds = max(1, int(args.ttl_seconds))
    except Exception:
        warn("FAIL error=INVALID_TTL_SECONDS")
        return 2
    chat = parse_reaper_bool(str(args.chat))

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    items: list[dict[str, Any]] = []
    if intake_path.exists():
        try:
            obj = json.loads(intake_path.read_text(encoding="utf-8"))
        except Exception:
            obj = {}
        if isinstance(obj, dict):
            items = obj.get("items") if isinstance(obj.get("items"), list) else []

    selection_source = ""
    if not intake_id:
        selected = [
            item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("intake_id"), str)
            and item.get("autopilot_selected") is True
        ]
        selected.sort(key=lambda item: str(item.get("intake_id") or ""))
        if selected:
            intake_id = str(selected[0].get("intake_id") or "")
            selection_source = "autopilot_selected"

    if not intake_id:
        candidates = [
            item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("intake_id"), str)
            and str(item.get("bucket") or "") == "TICKET"
            and str(item.get("status") or "").upper() in {"OPEN", "PLANNED"}
        ]
        candidates.sort(key=lambda item: str(item.get("intake_id") or ""))
        if candidates:
            intake_id = str(candidates[0].get("intake_id") or "")
            selection_source = "fallback_ticket"

    if not intake_id:
        warn("FAIL error=INTAKE_ID_REQUIRED")
        return 2

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = build_run_id(
        workspace_root=ws,
        op_name="work-item-lease-seed",
        inputs={"intake_id": intake_id, "owner": owner, "ttl_seconds": ttl_seconds},
        date_bucket=date_bucket_from_iso(generated_at),
    )
    lease_result = acquire_lease(
        workspace_root=ws,
        work_item_id=intake_id,
        run_id=run_id,
        owner=owner,
        ttl_seconds=ttl_seconds,
    )
    lease_status = str(lease_result.get("status") or "UNKNOWN")
    lease = lease_result.get("lease") if isinstance(lease_result.get("lease"), dict) else {}
    stale_cleared = lease_result.get("stale_cleared") if isinstance(lease_result.get("stale_cleared"), dict) else None

    report_rel = Path(".cache") / "reports" / "work_item_lease_seed.v1.json"
    report_path = ws / report_rel
    report = {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(ws),
        "intake_id": intake_id,
        "selection_source": selection_source,
        "lease_status": lease_status,
        "run_id": run_id,
        "owner": owner,
        "ttl_seconds": ttl_seconds,
        "lease_id": lease.get("lease_id"),
        "lease_path": str(Path(".cache") / "index" / "work_item_leases.v1.json"),
        "expires_at": lease.get("expires_at"),
        "heartbeat_at": lease.get("heartbeat_at"),
        "stale_cleared": stale_cleared,
        "notes": ["PROGRAM_LED=true", "NETWORK=false", "WORKSPACE_ONLY=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    payload = {
        "status": "OK" if lease_status in {"ACQUIRED", "LOCKED"} else "WARN",
        "lease_status": lease_status,
        "intake_id": intake_id,
        "run_id": run_id,
        "lease_id": lease.get("lease_id"),
        "report_path": report_rel.as_posix(),
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-item-lease-seed (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"lease_status={lease_status} intake_id={intake_id}")
        print("EVIDENCE:")
        print(str(report_rel))
        print("ACTIONS:")
        print(f"owner={owner} ttl_seconds={ttl_seconds}")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 2


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


def _load_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _is_stale(lock: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(str(lock.get("expires_at") or ""))
    if expires_at is None:
        return True
    return now >= expires_at


def cmd_doer_loop_lock_seed(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    owner = str(args.owner or "chat-proof").strip() or "chat-proof"
    run_id_arg = str(args.run_id).strip() if getattr(args, "run_id", None) else ""
    try:
        ttl_seconds = max(1, int(args.ttl_seconds))
    except Exception:
        warn("FAIL error=INVALID_TTL_SECONDS")
        return 2
    chat = parse_reaper_bool(str(args.chat))

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = run_id_arg or build_run_id(
        workspace_root=ws,
        op_name="doer-loop-lock-seed",
        inputs={"owner": owner, "ttl_seconds": ttl_seconds},
        date_bucket=date_bucket_from_iso(generated_at),
    )
    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    stale_cleared = False
    existing_lock: dict[str, Any] | None = None
    if lock_path.exists():
        try:
            existing_lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            existing_lock = None

    now = _parse_iso(generated_at) or datetime.now(timezone.utc).replace(microsecond=0)
    if isinstance(existing_lock, dict):
        expires_at = _parse_iso(str(existing_lock.get("expires_at") or ""))
        if expires_at and now < expires_at:
            payload = {
                "status": "LOCKED",
                "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
                "lock_id": existing_lock.get("lock_id") or existing_lock.get("lease_id"),
                "expires_at": existing_lock.get("expires_at"),
                "owner": existing_lock.get("owner_session") or existing_lock.get("owner_tag"),
                "run_id": existing_lock.get("run_id"),
            }
            if chat:
                print("PREVIEW:")
                print("PROGRAM-LED: doer-loop-lock-seed (workspace-only)")
                print(f"workspace_root={ws}")
                print("RESULT:")
                print("lock_status=LOCKED (existing lock preserved)")
                print("EVIDENCE:")
                print(str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"))
                print("ACTIONS:")
                print(f"owner={owner} ttl_seconds={ttl_seconds}")
                print("NEXT:")
                print("Devam et / Durumu göster / Duraklat")
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0
        stale_cleared = True

    expires_at = now + timedelta(seconds=int(ttl_seconds))
    lock_id = _hash_text(f"doer-loop-lock-seed-v0.4.1:{ws}:{owner}:{ttl_seconds}")
    payload = {
        "version": "v1",
        "lease_id": lock_id,
        "lock_id": lock_id,
        "owner_tag": owner,
        "owner_session": owner,
        "run_id": run_id,
        "acquired_at": generated_at,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "heartbeat_at": generated_at,
        "ttl_seconds": int(ttl_seconds),
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    clear_report_rel = None
    if stale_cleared:
        clear_report = {
            "version": "v1",
            "cleared_at": generated_at,
            "workspace_root": str(ws),
            "previous_lock": existing_lock,
            "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
        }
        clear_report_path = ws / ".cache" / "reports" / "doer_loop_lock_clear_stale.v1.json"
        clear_report_path.parent.mkdir(parents=True, exist_ok=True)
        clear_report_path.write_text(
            json.dumps(clear_report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        clear_report_rel = str(Path(".cache") / "reports" / "doer_loop_lock_clear_stale.v1.json")

    report_rel = Path(".cache") / "reports" / "doer_loop_lock_seed.v1.json"
    report_path = ws / report_rel
    report = {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(ws),
        "lock_id": lock_id,
        "run_id": run_id,
        "owner": owner,
        "ttl_seconds": int(ttl_seconds),
        "expires_at": payload.get("expires_at"),
        "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
        "stale_cleared": stale_cleared,
        "stale_clear_report": clear_report_rel,
        "notes": ["PROGRAM_LED=true", "NETWORK=false", "WORKSPACE_ONLY=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    result = {
        "status": "OK",
        "lock_status": "SEEDED",
        "lock_id": lock_id,
        "run_id": run_id,
        "report_path": report_rel.as_posix(),
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: doer-loop-lock-seed (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"lock_status=SEEDED lock_id={lock_id}")
        print("EVIDENCE:")
        print(str(report_rel))
        print("ACTIONS:")
        print(f"owner={owner} ttl_seconds={ttl_seconds}")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_doer_loop_lock_status(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    lock = _load_lock(lock_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    lock_status = "MISSING"
    parse_error = False
    if lock_path.exists() and lock is None:
        lock_status = "INVALID"
        parse_error = True
    elif isinstance(lock, dict):
        lock_status = "STALE" if _is_stale(lock, now) else "LOCKED"

    report_rel = Path(".cache") / "reports" / "doer_loop_lock_status.v1.json"
    report_path = ws / report_rel
    report = {
        "version": "v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "workspace_root": str(ws),
        "lock_status": lock_status,
        "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
        "owner_tag": str(lock.get("owner_tag") or "") if isinstance(lock, dict) else "",
        "owner_session": str(lock.get("owner_session") or "") if isinstance(lock, dict) else "",
        "expires_at": str(lock.get("expires_at") or "") if isinstance(lock, dict) else "",
        "run_id": str(lock.get("run_id") or "") if isinstance(lock, dict) else "",
        "parse_error": parse_error,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    status = "OK" if lock_status in {"LOCKED", "STALE", "MISSING"} else "WARN"
    result = {
        "status": status,
        "lock_status": lock_status,
        "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
        "report_path": report_rel.as_posix(),
    }
    if isinstance(lock, dict):
        result["owner_tag"] = str(lock.get("owner_tag") or "")
        result["expires_at"] = str(lock.get("expires_at") or "")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: doer-loop-lock-status (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"lock_status={lock_status}")
        print("EVIDENCE:")
        print(str(report_rel))
        print("ACTIONS:")
        print("read_only=true")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN"} else 2


def cmd_doer_loop_lock_clear(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    owner = str(args.owner or "").strip()
    mode = str(args.mode or "owner_or_stale").strip()
    if mode not in {"owner_or_stale", "owner_only", "stale_only"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    lock = _load_lock(lock_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    cleared = False
    clear_reason = ""
    lock_status = "MISSING"
    owner_found = ""
    expires_at = ""
    stale = False

    if lock_path.exists() and lock is None:
        lock_status = "INVALID"
        stale = True
    elif isinstance(lock, dict):
        lock_status = "LOCKED"
        owner_found = str(lock.get("owner_session") or lock.get("owner_tag") or "")
        expires_at = str(lock.get("expires_at") or "")
        stale = _is_stale(lock, now)

    owner_match = owner and owner_found and owner == owner_found
    allow_clear = False
    if lock_status == "MISSING":
        allow_clear = False
    elif mode == "owner_only":
        allow_clear = owner_match
    elif mode == "stale_only":
        allow_clear = stale
    else:
        allow_clear = owner_match or stale

    if allow_clear and lock_path.exists():
        try:
            lock_path.unlink()
            cleared = True
        except Exception:
            cleared = False

    if cleared:
        lock_status = "CLEARED"
        clear_reason = "stale" if stale and not owner_match else "owner"
    elif lock_status == "MISSING":
        clear_reason = "missing"
    elif lock_status == "LOCKED" and not allow_clear:
        lock_status = "NOT_OWNER" if owner and not owner_match else "NOT_STALE"
        clear_reason = "not_allowed"

    report_rel = Path(".cache") / "reports" / "doer_loop_lock_clear.v1.json"
    report_path = ws / report_rel
    report = {
        "version": "v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "workspace_root": str(ws),
        "lock_status": lock_status,
        "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
        "owner_requested": owner,
        "owner_found": owner_found,
        "expires_at": expires_at,
        "stale": stale,
        "cleared": cleared,
        "clear_reason": clear_reason,
        "previous_lock": lock if isinstance(lock, dict) else None,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    status = "OK" if cleared or lock_status in {"MISSING", "STALE", "CLEARED"} else "WARN"
    result = {
        "status": status,
        "lock_status": lock_status,
        "cleared": cleared,
        "report_path": report_rel.as_posix(),
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: doer-loop-lock-clear (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"lock_status={lock_status} cleared={cleared}")
        print("EVIDENCE:")
        print(str(report_rel))
        print("ACTIONS:")
        print(f"owner={owner} mode={mode}")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN"} else 2
