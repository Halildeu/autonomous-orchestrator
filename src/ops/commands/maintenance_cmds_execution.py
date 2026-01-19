from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_work_intake_exec_ticket(args: argparse.Namespace) -> int:
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
        limit = max(0, int(args.limit))
    except Exception:
        warn("FAIL error=INVALID_LIMIT")
        return 2
    chat = parse_reaper_bool(str(args.chat))

    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket

    res = run_work_intake_exec_ticket(workspace_root=ws, limit=limit)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    report_rel = res.get("work_intake_exec_path") if isinstance(res, dict) else None
    report_path = (ws / report_rel).resolve() if isinstance(report_rel, str) else None
    entries = []
    if report_path and report_path.exists():
        try:
            report_obj = json.loads(report_path.read_text(encoding="utf-8"))
            entries = report_obj.get("entries") if isinstance(report_obj.get("entries"), list) else []
        except Exception:
            entries = []

    payload = {
        "status": status,
        "error_code": res.get("error_code") if isinstance(res, dict) else None,
        "workspace_root": str(ws),
        "work_intake_exec_path": report_rel,
        "work_intake_exec_md_path": res.get("work_intake_exec_md_path") if isinstance(res, dict) else None,
        "selected_count": res.get("selected_count") if isinstance(res, dict) else 0,
        "applied_count": res.get("applied_count") if isinstance(res, dict) else 0,
        "planned_count": res.get("planned_count") if isinstance(res, dict) else 0,
        "idle_count": res.get("idle_count") if isinstance(res, dict) else 0,
        "ignored_count": res.get("ignored_count") if isinstance(res, dict) else 0,
        "skipped_count": res.get("skipped_count") if isinstance(res, dict) else 0,
        "decision_needed_count": res.get("decision_needed_count") if isinstance(res, dict) else 0,
        "entries_count": res.get("entries_count") if isinstance(res, dict) else 0,
    }
    skipped_by_reason = res.get("skipped_by_reason") if isinstance(res, dict) else None
    if isinstance(skipped_by_reason, dict):
        payload["skipped_by_reason"] = {str(k): int(v) for k, v in skipped_by_reason.items() if isinstance(v, int)}

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-exec-ticket (safe-only, workspace-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            f"status={payload.get('status')} applied={payload.get('applied_count')} "
            f"planned={payload.get('planned_count')} idle={payload.get('idle_count')}"
        )
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [payload.get("work_intake_exec_path"), payload.get("work_intake_exec_md_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        if entries:
            for item in entries[:5]:
                if not isinstance(item, dict):
                    continue
                print(f"{item.get('intake_id')} status={item.get('status')} action={item.get('action_kind')}")
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_auto_loop(args: argparse.Namespace) -> int:
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

    budget_raw = str(args.budget_seconds).strip() if getattr(args, "budget_seconds", None) is not None else ""
    if not budget_raw:
        warn("FAIL error=BUDGET_SECONDS_REQUIRED")
        return 2
    try:
        budget_seconds = int(budget_raw)
    except Exception:
        warn("FAIL error=INVALID_BUDGET_SECONDS")
        return 2
    if budget_seconds <= 0:
        warn("FAIL error=INVALID_BUDGET_SECONDS")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.ops.auto_loop import run_auto_loop

    payload = run_auto_loop(workspace_root=ws, budget_seconds=budget_seconds, chat=chat)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        doer_counts = counts.get("doer_counts") if isinstance(counts.get("doer_counts"), dict) else {}
        print("PREVIEW:")
        print("PROGRAM-LED: auto-loop (decision -> apply -> doer)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            "status={status} decisions_before={before} decisions_after={after}".format(
                status=payload.get("status"),
                before=counts.get("decision_pending_before", 0),
                after=counts.get("decision_pending_after", 0),
            )
        )
        print(
            "bulk_applied={bulk} selected={selected} doer_applied={applied}".format(
                bulk=counts.get("bulk_applied_count", 0),
                selected=counts.get("selected_count", 0),
                applied=doer_counts.get("applied", 0),
            )
        )
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        if isinstance(payload.get("self_heal"), dict) and payload.get("self_heal"):
            print("self_heal=ready")
        print("EVIDENCE:")
        for p in [
            payload.get("report_path"),
            payload.get("report_md_path"),
            payload.get("decision_inbox_path"),
            payload.get("bulk_apply_report_path"),
            payload.get("airunner_run_path"),
            payload.get("system_status_path"),
            payload.get("ui_snapshot_path"),
        ]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("decision-inbox-show")
        print("system-status")
        print("ui-snapshot-bundle")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2

