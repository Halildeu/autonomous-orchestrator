from __future__ import annotations

import argparse
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def _resolve_workspace(workspace_arg: str) -> Path | None:
    root = repo_root()
    raw = str(workspace_arg).strip()
    if not raw:
        return None
    ws = Path(raw)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        return None
    return ws


def cmd_auto_loop(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
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


def cmd_decision_inbox_show(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.ops.decision_inbox import run_decision_inbox_show

    payload = run_decision_inbox_show(workspace_root=ws)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: decision-inbox-show (build+read)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} decisions={payload.get('decisions_count', 0)}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
        if decisions:
            print("decisions:")
            for item in decisions:
                if not isinstance(item, dict):
                    continue
                print(
                    f"- {item.get('decision_id')} intake={item.get('source_intake_id')} kind={item.get('decision_kind')} default={item.get('default_option_id')}"
                )
        md_rel = payload.get("decision_inbox_md_path")
        if isinstance(md_rel, str) and md_rel:
            md_path = ws / md_rel
            if md_path.exists():
                try:
                    md_lines = md_path.read_text(encoding="utf-8").splitlines()
                except Exception:
                    md_lines = []
                if md_lines:
                    print("decision_inbox_md:")
                    for line in md_lines[:60]:
                        print(line)
        print("EVIDENCE:")
        for p in [payload.get("decision_inbox_path"), payload.get("decision_inbox_md_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("decision-apply-bulk")
        print("decision-apply")
        print("work-intake-check")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_work_intake_check(args: argparse.Namespace) -> int:
    root = repo_root()
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    detail = parse_reaper_bool(str(args.detail))

    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.work_intake_historical_prune import run_work_intake_historical_prune
    from src.ops.system_status_report import run_system_status
    from src.ops.roadmap_cli import cmd_portfolio_status

    historical_prune = run_work_intake_historical_prune(
        workspace_root=ws,
        core_root=root,
        dry_run=False,
        trigger="work-intake-check",
    )

    build_res = run_work_intake_build(workspace_root=ws)
    work_intake_path = build_res.get("work_intake_path") if isinstance(build_res, dict) else None

    intake_obj: dict[str, Any] = {}
    if isinstance(work_intake_path, str) and work_intake_path:
        intake_path_abs = (ws / work_intake_path).resolve()
        try:
            intake_obj = json.loads(intake_path_abs.read_text(encoding="utf-8"))
        except Exception:
            intake_obj = {}

    plan_policy = intake_obj.get("plan_policy") if isinstance(intake_obj.get("plan_policy"), str) else "optional"
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    summary = intake_obj.get("summary") if isinstance(intake_obj.get("summary"), dict) else {}
    counts_by_bucket = summary.get("counts_by_bucket") if isinstance(summary.get("counts_by_bucket"), dict) else {}
    top_next_actions = summary.get("top_next_actions") if isinstance(summary.get("top_next_actions"), list) else []
    next_intake_focus = summary.get("next_intake_focus") if isinstance(summary.get("next_intake_focus"), str) else "NONE"

    sys_result = run_system_status(workspace_root=ws, core_root=root, dry_run=False)
    sys_out = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    sys_rel = None
    if isinstance(sys_out, str):
        sys_rel = Path(sys_out).resolve()
        try:
            sys_rel = sys_rel.relative_to(ws)
        except Exception:
            sys_rel = None

    portfolio_buf = StringIO()
    with redirect_stdout(portfolio_buf), redirect_stderr(portfolio_buf):
        cmd_portfolio_status(argparse.Namespace(workspace_root=str(ws), mode="json"))
    portfolio_report = ws / ".cache" / "reports" / "portfolio_status.v1.json"
    portfolio_rel = ".cache/reports/portfolio_status.v1.json" if portfolio_report.exists() else ""

    status = build_res.get("status") if isinstance(build_res, dict) else "WARN"
    error_code = None
    plan_dir = ws / ".cache" / "reports" / "chg"
    plan_missing = False
    if plan_policy == "required" and items:
        if not plan_dir.exists():
            plan_missing = True
        else:
            plans = list(plan_dir.glob("CHG-INTAKE-*.plan.json"))
            plan_missing = not bool(plans)
        if plan_missing:
            status = "IDLE"
            error_code = "NO_PLAN_FOUND"

    payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "work_intake_path": work_intake_path,
        "items_count": len(items),
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions if detail else top_next_actions[:5],
        "next_intake_focus": next_intake_focus,
        "system_status_path": str(sys_rel) if isinstance(sys_rel, Path) else None,
        "portfolio_status_path": portfolio_rel,
        "notes": [f"mode={mode}", "PROGRAM_LED=true"],
    }
    if isinstance(historical_prune, dict):
        payload["historical_prune_status"] = str(historical_prune.get("status") or "UNKNOWN")
        report_path = historical_prune.get("report_path")
        if isinstance(report_path, str) and report_path:
            payload["historical_prune_report_path"] = report_path
        archived_count = historical_prune.get("archived_count")
        if isinstance(archived_count, int):
            payload["historical_prune_archived_count"] = int(archived_count)
        candidate_count = historical_prune.get("candidates_count")
        if isinstance(candidate_count, int):
            payload["historical_prune_candidates_count"] = int(candidate_count)

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-build + system-status + portfolio-status; user_command=false")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={status} items={len(items)} next_intake_focus={next_intake_focus}")
        if isinstance(historical_prune, dict):
            print(
                "historical_prune_status={status} archived={archived} candidates={candidates}".format(
                    status=historical_prune.get("status"),
                    archived=historical_prune.get("archived_count", 0),
                    candidates=historical_prune.get("candidates_count", 0),
                )
            )
        if error_code:
            print(f"error_code={error_code}")
        print("EVIDENCE:")
        for p in [
            payload.get("historical_prune_report_path"),
            work_intake_path,
            payload.get("system_status_path"),
            portfolio_rel,
        ]:
            if p:
                print(str(p))
        print("ACTIONS:")
        if plan_missing:
            print("auto-plan_uret")
            print("yeni_plan_ekle")
            print("durumu_goster")
        else:
            if top_next_actions:
                for item in top_next_actions[:5]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"{item.get('intake_id')} bucket={item.get('bucket')} "
                        f"priority={item.get('priority')}"
                    )
            else:
                print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_work_intake_historical_prune(args: argparse.Namespace) -> int:
    root = repo_root()
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    try:
        dry_run = parse_reaper_bool(str(getattr(args, "dry_run", "false")))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    from src.ops.work_intake_historical_prune import run_work_intake_historical_prune

    payload = run_work_intake_historical_prune(
        workspace_root=ws,
        core_root=root,
        dry_run=bool(dry_run),
        trigger="manual",
    )
    status = str(payload.get("status") or "WARN") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-historical-prune (workspace-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            "status={status} archived={archived} candidates={candidates}".format(
                status=payload.get("status"),
                archived=payload.get("archived_count", 0),
                candidates=payload.get("candidates_count", 0),
            )
        )
        print("EVIDENCE:")
        for p in [payload.get("jobs_index_path"), payload.get("report_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("work-intake-check")
        print("system-status")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "IDLE", "WOULD_WRITE"} else 2


def cmd_work_intake_exec_ticket(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
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


def cmd_decision_inbox_build(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.ops.decision_inbox import run_decision_inbox_build

    res = run_decision_inbox_build(workspace_root=ws)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    payload = {
        "status": status,
        "error_code": res.get("error_code") if isinstance(res, dict) else None,
        "workspace_root": str(ws),
        "decision_inbox_path": res.get("decision_inbox_path") if isinstance(res, dict) else None,
        "decision_inbox_md_path": res.get("decision_inbox_md_path") if isinstance(res, dict) else None,
        "decisions_count": res.get("decisions_count") if isinstance(res, dict) else 0,
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: decision-inbox-build (read-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} decisions={payload.get('decisions_count')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [payload.get("decision_inbox_path"), payload.get("decision_inbox_md_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        if payload.get("decisions_count", 0) > 0:
            print("decision_apply")
            print("durumu_goster")
        else:
            print("no_decisions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_decision_apply(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    decision_id = str(args.decision_id).strip()
    option_id = str(args.option_id).strip()
    if not decision_id:
        warn("FAIL error=DECISION_ID_REQUIRED")
        return 2
    if not option_id:
        warn("FAIL error=OPTION_ID_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.ops.decision_inbox import run_decision_apply

    res = run_decision_apply(workspace_root=ws, decision_id=decision_id, option_id=option_id)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    payload = {
        "status": status,
        "error_code": res.get("error_code") if isinstance(res, dict) else None,
        "workspace_root": str(ws),
        "decision_id": res.get("decision_id") if isinstance(res, dict) else decision_id,
        "decision_kind": res.get("decision_kind") if isinstance(res, dict) else "",
        "option_id": res.get("option_id") if isinstance(res, dict) else option_id,
        "decisions_applied_path": res.get("decisions_applied_path") if isinstance(res, dict) else None,
        "selection_path": res.get("selection_path") if isinstance(res, dict) else None,
        "policy_override_path": res.get("policy_override_path") if isinstance(res, dict) else None,
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: decision-apply (workspace-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} decision={payload.get('decision_id')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [payload.get("decisions_applied_path"), payload.get("selection_path"), payload.get("policy_override_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("work-intake-check")
        print("airrunner-run")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_decision_seed(args: argparse.Namespace) -> int:
    ws = _resolve_workspace(str(getattr(args, "workspace_root", "") or ""))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    decision_kind = str(args.kind).strip()
    target = str(args.target).strip()
    if not decision_kind:
        warn("FAIL error=DECISION_KIND_REQUIRED")
        return 2
    if not target:
        warn("FAIL error=DECISION_TARGET_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.ops.decision_inbox import run_decision_seed

    res = run_decision_seed(workspace_root=ws, decision_kind=decision_kind, target=target)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    payload = {
        "status": status,
        "workspace_root": str(ws),
        "decision_kind": res.get("decision_kind") if isinstance(res, dict) else decision_kind,
        "target": res.get("target") if isinstance(res, dict) else target,
        "seed_id": res.get("seed_id") if isinstance(res, dict) else "",
        "seed_path": res.get("seed_path") if isinstance(res, dict) else None,
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: decision-seed (workspace-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} seed_id={payload.get('seed_id')}")
        print("EVIDENCE:")
        if payload.get("seed_path"):
            print(str(payload.get("seed_path")))
        print("ACTIONS:")
        print("decision-inbox-build")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2
