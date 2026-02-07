from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool
from src.ops.work_item_claims import get_active_claim
from src.ops.work_item_state import (
    FINAL_STATES,
    STATE_CLOSED,
    STATE_OPEN,
    get_state_entry,
    record_run,
    update_state,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_state_path() -> str:
    return str(Path(".cache") / "index" / "work_item_state.v1.json")


def _rel_runs_path() -> str:
    return str(Path(".cache") / "index" / "work_item_runs.v1.jsonl")


def _rel_work_intake_path() -> str:
    return str(Path(".cache") / "index" / "work_intake.v1.json")


def _fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _find_intake_item(workspace_root: Path, intake_id: str) -> dict[str, Any] | None:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        return None
    try:
        obj = _load_json(intake_path)
    except Exception:
        return None
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("intake_id") or "") == intake_id:
            return dict(item)
    return None


def cmd_work_intake_close(args: argparse.Namespace) -> int:
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

    intake_id = str(getattr(args, "intake_id", "") or "").strip()
    if not intake_id:
        warn("FAIL error=INTAKE_ID_REQUIRED")
        return 2

    mode = str(getattr(args, "mode", "close") or "close").strip().lower()
    if mode not in {"close", "reopen", "status"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    reason = str(getattr(args, "reason", "") or "").strip()

    owner_tag = str(getattr(args, "owner_tag", "") or "").strip()
    if not owner_tag:
        owner_tag = str(os.environ.get("CODEX_CHAT_TAG") or "").strip() or "unknown"

    force = parse_reaper_bool(str(getattr(args, "force", "false") or "false"))

    item = _find_intake_item(ws, intake_id)
    if not isinstance(item, dict):
        warn("FAIL error=WORK_INTAKE_ITEM_NOT_FOUND")
        return 2

    bucket = str(item.get("bucket") or "")
    source_type = str(item.get("source_type") or "")
    if bucket != "TICKET" or source_type != "MANUAL_REQUEST":
        warn("FAIL error=CLOSE_NOT_ALLOWED_FOR_ITEM")
        return 2

    state_entry = get_state_entry(ws, intake_id)
    prev_state = str(state_entry.get("state") or STATE_OPEN) if isinstance(state_entry, dict) else STATE_OPEN
    prev_state_at = str(state_entry.get("last_updated_at") or "") if isinstance(state_entry, dict) else ""

    if mode == "status":
        payload = {
            "status": "OK",
            "mode": "status",
            "workspace_root": str(ws),
            "intake_id": intake_id,
            "bucket": bucket,
            "source_type": source_type,
            "state": prev_state,
            "state_updated_at": prev_state_at,
            "work_intake_path": _rel_work_intake_path(),
            "work_item_state_path": _rel_state_path(),
            "work_item_runs_path": _rel_runs_path(),
            "generated_at": _now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    claim = get_active_claim(ws, intake_id)
    if isinstance(claim, dict):
        claim_owner = str(claim.get("owner_tag") or "")
        if claim_owner and claim_owner != owner_tag and not force:
            payload = {
                "status": "FAIL",
                "error_code": "CLAIMED_BY_OTHER",
                "mode": mode,
                "workspace_root": str(ws),
                "intake_id": intake_id,
                "owner_tag": owner_tag,
                "force": False,
                "claim": {"owner_tag": claim_owner, "expires_at": str(claim.get("expires_at") or "")},
                "generated_at": _now_iso(),
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 2

    if mode == "close" and prev_state in FINAL_STATES:
        payload = {
            "status": "OK",
            "mode": "close",
            "workspace_root": str(ws),
            "intake_id": intake_id,
            "owner_tag": owner_tag,
            "force": bool(force),
            "result": "NOOP_ALREADY_FINAL",
            "previous_state": prev_state,
            "state_updated_at": prev_state_at,
            "work_intake_path": _rel_work_intake_path(),
            "work_item_state_path": _rel_state_path(),
            "work_item_runs_path": _rel_runs_path(),
            "generated_at": _now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if mode == "reopen" and prev_state != STATE_CLOSED:
        payload = {
            "status": "OK",
            "mode": "reopen",
            "workspace_root": str(ws),
            "intake_id": intake_id,
            "owner_tag": owner_tag,
            "force": bool(force),
            "result": "NOOP_NOT_CLOSED",
            "previous_state": prev_state,
            "state_updated_at": prev_state_at,
            "work_intake_path": _rel_work_intake_path(),
            "work_item_state_path": _rel_state_path(),
            "work_item_runs_path": _rel_runs_path(),
            "generated_at": _now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    next_state = STATE_CLOSED if mode == "close" else STATE_OPEN
    note = reason or ("explicit_close" if next_state == STATE_CLOSED else "explicit_reopen")
    fp = _fingerprint({"mode": mode, "intake_id": intake_id, "owner_tag": owner_tag, "note": note})

    rel_state = _rel_state_path()
    rel_runs = _rel_runs_path()
    rel_intake = _rel_work_intake_path()
    evidence_paths = [rel_intake, rel_state, rel_runs]

    entry = update_state(
        workspace_root=ws,
        work_item_id=intake_id,
        state=next_state,
        run_id=fp,
        fingerprint=fp,
        evidence_paths=evidence_paths,
        note=note,
    )
    record_run(
        workspace_root=ws,
        run_id=fp,
        work_item_id=intake_id,
        fingerprint=fp,
        state=next_state,
        result="OK",
        evidence_paths=evidence_paths,
    )

    payload = {
        "status": "OK",
        "mode": mode,
        "workspace_root": str(ws),
        "intake_id": intake_id,
        "bucket": bucket,
        "source_type": source_type,
        "owner_tag": owner_tag,
        "force": bool(force),
        "reason": reason,
        "previous_state": prev_state,
        "next_state": next_state,
        "work_item_state_entry": entry if isinstance(entry, dict) else {},
        "evidence_paths": evidence_paths,
        "generated_at": _now_iso(),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0

