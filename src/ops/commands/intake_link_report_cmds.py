from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_intake_link_report(args: argparse.Namespace) -> int:
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

    req_id = str(args.req_id or "").strip()
    if not req_id:
        warn("FAIL error=REQ_ID_REQUIRED")
        return 2

    try:
        write_plan = parse_reaper_bool(str(getattr(args, "write_plan", "false")))
    except ValueError:
        warn("FAIL error=INVALID_WRITE_PLAN")
        return 2

    try:
        chat = parse_reaper_bool(str(getattr(args, "chat", "true")))
    except ValueError:
        warn("FAIL error=INVALID_CHAT")
        return 2

    from src.ops.intake_link_report import run_intake_link_report

    payload = run_intake_link_report(
        workspace_root=ws,
        req_id=req_id,
        write_plan=bool(write_plan),
    )

    status = payload.get("status") if isinstance(payload, dict) else None
    if chat and isinstance(payload, dict):
        report_path = payload.get("report_path")
        md_path = payload.get("report_md_path")
        plan_path = payload.get("plan_path")
        print("PREVIEW:")
        print("PROGRAM-LED: intake-link-report (read-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status={payload.get('status')} match_count={payload.get('match_count')}")
        if payload.get("status") == "WARN":
            print("note=NO_MATCH_FOUND")
        print("EVIDENCE:")
        for p in [report_path, md_path, plan_path]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("work-intake-check")
        print("decision-inbox-build")
        print("system-status")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN"} else 2
