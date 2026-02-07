from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_work_intake_autoselect(args: argparse.Namespace) -> int:
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

    try:
        limit = int(args.limit)
    except Exception:
        warn("FAIL error=INVALID_LIMIT")
        return 2

    mode = str(getattr(args, "mode", "policy") or "policy").strip().lower()
    scope = str(getattr(args, "scope", "") or "").strip().lower()
    if scope:
        if scope in {"safe_only", "safe-first", "safe_first"}:
            mode = "safe_first"
        elif scope == "policy":
            mode = "policy"
        else:
            warn("FAIL error=INVALID_SCOPE")
            return 2
    if mode not in {"policy", "safe_first"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.work_intake_autoselect import run_work_intake_autoselect

    res = run_work_intake_autoselect(workspace_root=ws, limit=limit, mode=mode)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    status = res.get("status") if isinstance(res, dict) else None
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_doer_actionability(args: argparse.Namespace) -> int:
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

    out = str(getattr(args, "out", "auto") or "auto")
    chat = parse_reaper_bool(str(getattr(args, "chat", "true")))

    from src.ops.doer_actionability import run_doer_actionability

    payload = run_doer_actionability(workspace_root=ws, out=out)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        print("PREVIEW:")
        print("PROGRAM-LED: doer-actionability (read-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} candidates={counts.get('candidate_total', 0)}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [payload.get("report_path"), payload.get("report_md_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("work-intake-autoselect")
        print("airrunner-run")
        print("system-status")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2
