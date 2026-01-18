from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool
from src.ops.work_item_claims import acquire_claim, load_claims, release_claim


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel_claim_path() -> str:
    return str(Path(".cache") / "index" / "work_item_claims.v1.json")


def _active_claim_for(workspace_root: Path, intake_id: str) -> dict | None:
    now = datetime.now(timezone.utc)
    for claim in load_claims(workspace_root):
        if str(claim.get("work_item_id") or "") != str(intake_id or ""):
            continue
        expires_at = str(claim.get("expires_at") or "")
        if not expires_at:
            continue
        # Stale claims are treated as absent (fail-closed).
        try:
            raw = expires_at.replace("Z", "+00:00") if expires_at.endswith("Z") else expires_at
            exp = datetime.fromisoformat(raw)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            exp = exp.astimezone(timezone.utc)
            if now >= exp:
                continue
        except Exception:
            continue
        return claim
    return None


def cmd_work_intake_claim(args: argparse.Namespace) -> int:
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

    mode = str(getattr(args, "mode", "claim") or "claim").strip().lower()
    if mode not in {"claim", "release", "status"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    owner_tag = str(getattr(args, "owner_tag", "") or "").strip()
    if not owner_tag:
        owner_tag = str(os.environ.get("CODEX_CHAT_TAG") or "").strip() or "unknown"

    force = parse_reaper_bool(str(getattr(args, "force", "false") or "false"))

    ttl_seconds = 3600
    if getattr(args, "ttl_seconds", None) is not None:
        try:
            ttl_seconds = max(1, int(args.ttl_seconds))
        except Exception:
            warn("FAIL error=INVALID_TTL_SECONDS")
            return 2

    if mode == "status":
        claim = _active_claim_for(ws, intake_id)
        payload = {
            "status": "OK",
            "mode": "status",
            "workspace_root": str(ws),
            "intake_id": intake_id,
            "claim_status": "CLAIMED" if isinstance(claim, dict) else "FREE",
            "claim": claim or {},
            "claims_path": _rel_claim_path(),
            "generated_at": _now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if mode == "release":
        res = release_claim(workspace_root=ws, work_item_id=intake_id, owner_tag=owner_tag, force=force)
        status = str(res.get("status") or "UNKNOWN")
        claim = res.get("claim") if isinstance(res.get("claim"), dict) else {}
        out_status = "OK" if status in {"RELEASED", "RELEASED_FORCED", "NOOP"} else "WARN"
        payload = {
            "status": out_status,
            "mode": "release",
            "workspace_root": str(ws),
            "intake_id": intake_id,
            "owner_tag": owner_tag,
            "force": bool(force),
            "result": status,
            "claim": claim,
            "claims_path": _rel_claim_path(),
            "generated_at": _now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if out_status in {"OK", "WARN"} else 2

    res = acquire_claim(workspace_root=ws, work_item_id=intake_id, owner_tag=owner_tag, ttl_seconds=ttl_seconds)
    status = str(res.get("status") or "UNKNOWN")
    claim = res.get("claim") if isinstance(res.get("claim"), dict) else {}
    stale_cleared = res.get("stale_cleared") if isinstance(res.get("stale_cleared"), dict) else None

    out_status = "OK" if status in {"ACQUIRED", "RENEWED"} else "WARN"
    error_code = "CLAIMED_BY_OTHER" if status == "LOCKED" else None
    payload = {
        "status": out_status,
        "error_code": error_code,
        "mode": "claim",
        "workspace_root": str(ws),
        "intake_id": intake_id,
        "owner_tag": owner_tag,
        "ttl_seconds": ttl_seconds,
        "result": status,
        "claim": claim,
        "stale_cleared": stale_cleared,
        "claims_path": _rel_claim_path(),
        "generated_at": _now_iso(),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if out_status in {"OK", "WARN"} else 2

