from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_work_intake_select(args: argparse.Namespace) -> int:
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

    mode = str(getattr(args, "mode", "select") or "select").strip().lower()
    if mode not in {"select", "clear"}:
        warn("FAIL error=INVALID_MODE")
        return 2
    backup = parse_reaper_bool(str(getattr(args, "backup", "false")))

    selection_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    selection_rel = str(Path(".cache") / "index" / "work_intake_selection.v1.json")
    if mode == "clear":
        if not selection_path.exists():
            out_payload = {
                "status": "IDLE",
                "error_code": "NO_SELECTION_FILE",
                "workspace_root": str(ws),
                "selection_path": selection_rel,
                "backup_path": "",
                "cleared_count": 0,
                "selected_ids": [],
                "selected_count": 0,
            }
            print(json.dumps(out_payload, ensure_ascii=False, sort_keys=True))
            return 0

        try:
            selection_raw = selection_path.read_text(encoding="utf-8")
        except Exception:
            selection_raw = ""
        try:
            obj = json.loads(selection_raw) if selection_raw else {}
        except Exception:
            obj = {}
        raw_ids = obj.get("selected_ids") if isinstance(obj, dict) else None
        if not isinstance(raw_ids, list):
            raw_ids = obj.get("intake_ids") if isinstance(obj, dict) else None
        selected_ids = [str(x) for x in raw_ids if isinstance(x, str) and x.strip()] if isinstance(raw_ids, list) else []
        cleared_count = len(selected_ids)

        backup_path = ""
        if backup:
            backup_name = f"{selection_path.name}.bak.1"
            for item in selection_path.parent.glob(f"{selection_path.name}.bak*"):
                try:
                    item.unlink()
                except Exception:
                    pass
            backup_path_obj = selection_path.with_name(backup_name)
            backup_path_obj.write_text(selection_raw, encoding="utf-8")
            backup_path = str(Path(".cache") / "index" / backup_name)

        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = {
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(ws),
            "selected_ids": [],
            "content_hash": hashlib.sha256(
                json.dumps([], ensure_ascii=True, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "notes": ["PROGRAM_LED=true", "CLEARED=true"],
        }
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        status = "OK" if cleared_count > 0 else "IDLE"
        error_code = None if cleared_count > 0 else "NO_SELECTED_IDS"
        out_payload = {
            "status": status,
            "error_code": error_code,
            "workspace_root": str(ws),
            "selection_path": selection_rel,
            "backup_path": backup_path,
            "cleared_count": cleared_count,
            "selected_ids": [],
            "selected_count": 0,
        }
        print(json.dumps(out_payload, ensure_ascii=False, sort_keys=True))
        return 0

    intake_id = str(getattr(args, "intake_id", "")).strip()
    if not intake_id:
        warn("FAIL error=INTAKE_ID_REQUIRED")
        return 2

    selected = parse_reaper_bool(str(args.selected))
    selected_ids: list[str] = []
    if selection_path.exists():
        try:
            obj = json.loads(selection_path.read_text(encoding="utf-8"))
        except Exception:
            obj = {}
        raw_ids = obj.get("selected_ids") if isinstance(obj, dict) else None
        if not isinstance(raw_ids, list):
            raw_ids = obj.get("intake_ids") if isinstance(obj, dict) else None
        if isinstance(raw_ids, list):
            selected_ids = [str(x) for x in raw_ids if isinstance(x, str) and x.strip()]

    before_set = set(selected_ids)
    if selected:
        before_set.add(intake_id)
    else:
        before_set.discard(intake_id)
    selected_ids = sorted(before_set)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(ws),
        "selected_ids": selected_ids,
        "content_hash": hashlib.sha256(
            json.dumps(selected_ids, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "notes": ["PROGRAM_LED=true"],
    }
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    status = "OK"
    error_code = None
    if not selected_ids:
        status = "IDLE"
        error_code = "NO_SELECTED_IDS"

    out_payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "selection_path": selection_rel,
        "backup_path": "",
        "cleared_count": 0,
        "selected_ids": selected_ids,
        "selected_count": len(selected_ids),
    }
    print(json.dumps(out_payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2
