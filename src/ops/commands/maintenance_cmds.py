from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, run_step, warn
from src.ops.commands.context_cmds import register_context_subcommands
from src.ops.commands.maintenance_doc_cmds import (
    cmd_doc_graph,
    cmd_doc_nav_check,
    cmd_doc_nav_job_poll,
    cmd_doc_nav_job_start,
)
from src.ops.commands.maintenance_lease_cmds import (
    cmd_doer_loop_lock_clear,
    cmd_doer_loop_lock_seed,
    cmd_doer_loop_lock_status,
    cmd_work_item_lease_seed,
)
from src.ops.commands.maintenance_cmds_doer import cmd_doer_actionability, cmd_work_intake_autoselect
from src.ops.commands.maintenance_cmds_planner import register_planner_and_intake_subcommands
from src.ops.commands.intake_link_report_cmds import cmd_intake_link_report
from src.ops.commands.maintenance_policy_cmds import cmd_evidence_export, cmd_policy_check, cmd_reaper
from src.ops.commands.work_intake_claim_cmds import cmd_work_intake_claim
from src.ops.commands.work_intake_close_cmds import cmd_work_intake_close
from src.ops.commands.work_intake_select_cmds import cmd_work_intake_select
from src.ops.reaper import parse_bool as parse_reaper_bool


def _parse_notes_tags(raw: str) -> list[str]:
    if not isinstance(raw, str):
        return []
    parts = raw.replace("\n", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def _parse_notes_links(raw: str) -> list[dict[str, Any]] | None:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        target = item.get("id_or_path")
        if isinstance(kind, str) and isinstance(target, str) and kind.strip() and target.strip():
            out.append({"kind": kind.strip(), "id_or_path": target.strip()})
    return out


def _normalize_script_budget_report(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"status": "FAIL", "hard_exceeded": 0, "soft_exceeded": 0}
    exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
    exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []
    function_soft = report.get("function_soft") if isinstance(report.get("function_soft"), list) else []
    hard_exceeded = len(exceeded_hard) + len(function_hard)
    soft_exceeded = len(exceeded_soft) + len(function_soft)
    report["hard_exceeded"] = hard_exceeded
    report["soft_exceeded"] = soft_exceeded
    report.setdefault("soft_only", hard_exceeded == 0 and soft_exceeded > 0)
    return report
def cmd_script_budget(args: argparse.Namespace) -> int:
    root = repo_root()

    out_arg = str(args.out).strip() if getattr(args, "out", None) else ""
    if out_arg:
        out_path = Path(out_arg)
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    else:
        out_path = (root / ".cache" / "script_budget" / "report.json").resolve()

    rc, _, _ = run_step(
        root,
        [sys.executable, str(root / "ci" / "check_script_budget.py"), "--out", str(out_path)],
        stage="SCRIPT_BUDGET",
    )

    status = "FAIL"
    hard_exceeded = 0
    soft_exceeded = 0
    try:
        report = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(report, dict):
            report = _normalize_script_budget_report(report)
            status = str(report.get("status") or "FAIL")
            hard_exceeded = int(report.get("hard_exceeded", hard_exceeded) or 0)
            soft_exceeded = int(report.get("soft_exceeded", soft_exceeded) or 0)
            out_path.write_text(
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
    except Exception:
        pass

    try:
        out_display = out_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        out_display = str(out_path)
    print(f"SCRIPT_BUDGET status={status} hard_exceeded={hard_exceeded} soft_exceeded={soft_exceeded} report={out_display}")

    return 0 if int(rc) == 0 and status in {"OK", "WARN"} else 2
def cmd_smoke(args: argparse.Namespace) -> int:
    root = repo_root()
    level = str(args.level).strip().lower()
    if level not in {"fast", "full"}:
        warn("FAIL error=INVALID_LEVEL")
        return 2

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = level
    proc = subprocess.run([sys.executable, "smoke_test.py"], cwd=root, text=True, env=env)
    status = "OK" if proc.returncode == 0 else "FAIL"
    print(json.dumps({"status": status, "level": level}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 2
def cmd_system_status(args: argparse.Namespace) -> int:
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
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    from src.ops.system_status_report import run_system_status

    res = run_system_status(workspace_root=ws, core_root=root, dry_run=bool(dry_run))
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE", "WARN"} else 2
def cmd_ui_snapshot(args: argparse.Namespace) -> int:
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

    out = str(args.out) if args.out else ""

    from src.ops.ui_snapshot_bundle import run_ui_snapshot_bundle

    payload = run_ui_snapshot_bundle(workspace_root=ws, out=out or None)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2
def cmd_cockpit_serve(args: argparse.Namespace) -> int:
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

    host = str(args.host or "127.0.0.1")
    try:
        port = int(args.port)
    except Exception:
        port = 8787

    server_path = root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "server.py"
    if not server_path.exists():
        warn("FAIL error=COCKPIT_SERVER_MISSING")
        return 2

    cmd = [sys.executable, str(server_path), "--workspace-root", str(ws), "--port", str(port), "--host", host]
    return int(subprocess.call(cmd, cwd=root))

def cmd_cockpit_healthcheck(args: argparse.Namespace) -> int:
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
        port = int(str(args.port or "8787"))
    except Exception:
        port = 8787

    from src.ops.cockpit_healthcheck import run_cockpit_healthcheck

    res = run_cockpit_healthcheck(workspace_root=ws, port=port)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2


def cmd_planner_notes_create(args: argparse.Namespace) -> int:
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

    title = str(args.title or "")
    body = str(args.body or "")
    tags = _parse_notes_tags(str(args.tags or ""))
    links_raw = str(getattr(args, "links_json", "") or "")
    links = _parse_notes_links(links_raw)
    if links is None:
        warn("FAIL error=LINKS_JSON_INVALID")
        return 2

    from src.ops.planner_notes import run_planner_notes_create

    res = run_planner_notes_create(workspace_root=ws, title=title, body=body, tags=tags, links=links)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "IDLE", "WARN"} else 2


def cmd_planner_notes_delete(args: argparse.Namespace) -> int:
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

    note_id = str(args.note_id or "").strip()
    if not note_id:
        warn("FAIL error=NOTE_ID_REQUIRED")
        return 2

    from src.ops.planner_notes import run_planner_notes_delete

    res = run_planner_notes_delete(workspace_root=ws, note_id=note_id)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "IDLE", "WARN"} else 2

def cmd_preflight_stamp(args: argparse.Namespace) -> int:
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

    mode = str(args.mode or "write").strip().lower()
    if mode not in {"write", "read"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.preflight_stamp import run_preflight_stamp

    payload = run_preflight_stamp(workspace_root=ws, mode=mode)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else None
    return 0 if status in {"OK", "WARN", "IDLE"} else 2

def cmd_integrity_verify(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.integrity_verify import run_integrity_verify

    res = run_integrity_verify(workspace_root=ws, mode=mode)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    verify = res.get("verify_on_read_result") if isinstance(res, dict) else None
    if mode == "strict" and verify == "FAIL":
        return 2
    return 0 if res.get("status") in {"OK", "SKIPPED"} else 2

def cmd_work_intake_build(args: argparse.Namespace) -> int:
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

    from src.ops.work_intake_from_sources import run_work_intake_build

    res = run_work_intake_build(workspace_root=ws)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    status = res.get("status") if isinstance(res, dict) else None
    return 0 if status in {"OK", "WARN", "IDLE"} else 2

def cmd_work_intake_check(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    detail = parse_reaper_bool(str(args.detail))

    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status
    from src.ops.roadmap_cli import cmd_portfolio_status

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

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-build + system-status + portfolio-status; user_command=false")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={status} items={len(items)} next_intake_focus={next_intake_focus}")
        if error_code:
            print(f"error_code={error_code}")
        print("EVIDENCE:")
        for p in [work_intake_path, payload.get("system_status_path"), portfolio_rel]:
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

def cmd_decision_inbox_build(args: argparse.Namespace) -> int:
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

def cmd_decision_inbox_show(args: argparse.Namespace) -> int:
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

def cmd_decision_apply(args: argparse.Namespace) -> int:
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

def cmd_decision_apply_bulk(args: argparse.Namespace) -> int:
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

    mode = str(args.mode or "safe_defaults").strip().lower()
    raw_ids = str(args.decision_ids or "")
    decision_ids = [chunk.strip() for chunk in raw_ids.replace(",", " ").split() if chunk.strip()]
    if decision_ids:
        mode = "decision_ids"

    from src.ops.decision_inbox import run_decision_apply_bulk

    payload = run_decision_apply_bulk(workspace_root=ws, mode=mode, decision_ids=decision_ids)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2

def cmd_decision_seed(args: argparse.Namespace) -> int:
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

def cmd_layer_boundary_check(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.ops.layer_boundary_check import run_layer_boundary_check

    res = run_layer_boundary_check(workspace_root=ws, mode=mode)
    if chat:
        print("PREVIEW:")
        print(f"PROGRAM-LED: layer-boundary-check mode={mode}; user_command=false")
        print(f"workspace_root={res.get('workspace_root')}")
        print("RESULT:")
        print(f"status={res.get('status')} would_block={res.get('would_block_count', 0)}")
        print("EVIDENCE:")
        for p in res.get("evidence_paths", []):
            print(str(p))
        print("ACTIONS:")
        if int(res.get("would_block_count", 0)) > 0:
            print("review_would_block_paths")
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2

def cmd_promotion_bundle(args: argparse.Namespace) -> int:
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
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    mode = str(args.mode).strip() if getattr(args, "mode", None) else ""

    from src.ops.promotion_bundle import run_promotion_bundle

    res = run_promotion_bundle(
        workspace_root=ws,
        core_root=root,
        mode=mode if mode else None,
        dry_run=bool(dry_run),
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE", "WARN"} else 2

def cmd_repo_hygiene(args: argparse.Namespace) -> int:
    root = repo_root()
    mode = str(args.mode).strip().lower()
    if mode not in {"report", "suggest"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    layout_arg = str(args.layout).strip() if args.layout else "docs/OPERATIONS/repo-layout.v1.json"
    out_arg = str(args.out).strip() if args.out else ".cache/repo_hygiene/report.json"

    layout_path = Path(layout_arg)
    if not layout_path.is_absolute():
        layout_path = (root / layout_path).resolve()
    out_path = Path(out_arg)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    from src.ops.repo_hygiene import run_repo_hygiene

    res = run_repo_hygiene(
        repo_root=root,
        layout_path=layout_path,
        out_path=out_path,
        mode=mode,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2
def cmd_airunner_time_sinks_prune(args: argparse.Namespace) -> int:
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
        max_age_seconds = int(str(args.max_age_seconds))
    except Exception:
        warn("FAIL error=INVALID_MAX_AGE_SECONDS")
        return 2

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    from src.ops.maintenance_time_sinks import prune_time_sinks_report

    res = prune_time_sinks_report(
        workspace_root=ws,
        max_age_seconds=max_age_seconds,
        dry_run=bool(dry_run),
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "IDLE", "WOULD_WRITE"} else 2

def register_maintenance_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_reaper = parent.add_parser("reaper", help="Run retention reaper (dry-run supported).")
    ap_reaper.add_argument("--dry-run", default="true", help="true|false")
    ap_reaper.add_argument("--now", help="ISO8601 timestamp (optional).")
    ap_reaper.add_argument("--out", help="Optional report JSON output path.")
    ap_reaper.set_defaults(func=cmd_reaper)
    ap_export = parent.add_parser("evidence-export", help="Export one evidence run as a zip (integrity-checked).")
    ap_export.add_argument("--run", required=True, help="Run id or path to evidence/<run_id> directory.")
    ap_export.add_argument("--out", required=True, help="Output zip path.")
    ap_export.add_argument("--force", default="false", help="true|false (default: false).")
    ap_export.set_defaults(func=cmd_evidence_export)
    ap_pc = parent.add_parser("policy-check", help="Validate + simulate policy impact (safe local workflow).")
    ap_pc.add_argument("--source", choices=["fixtures", "evidence", "both"], default="fixtures")
    ap_pc.add_argument("--baseline", default="HEAD~1", help="Git ref for baseline (default: HEAD~1).")
    ap_pc.add_argument("--fixtures", default="fixtures/envelopes")
    ap_pc.add_argument("--evidence", default="evidence")
    ap_pc.add_argument("--outdir", default=".cache/policy_check")
    ap_pc.set_defaults(func=cmd_policy_check)
    ap_sb = parent.add_parser("script-budget", help="Run Script Budget guardrails (soft=warn, hard=fail).")
    ap_sb.add_argument("--out", default=".cache/script_budget/report.json", help="Report JSON output path.")
    ap_sb.set_defaults(func=cmd_script_budget)
    ap_ts = parent.add_parser(
        "airunner-time-sinks-prune",
        help="Prune stale time_sinks report entries (workspace-only).",
    )
    ap_ts.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ts.add_argument("--max-age-seconds", default="86400", help="Max sink age in seconds (default: 86400).")
    ap_ts.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_ts.set_defaults(func=cmd_airunner_time_sinks_prune)
    ap_smoke = parent.add_parser("smoke", help="Run smoke_test.py with SMOKE_LEVEL (fast|full).")
    ap_smoke.add_argument("--level", default="fast", help="fast|full (default: fast).")
    ap_smoke.set_defaults(func=cmd_smoke)
    ap_sys = parent.add_parser("system-status", help="Generate unified system status report (JSON + MD).")
    ap_sys.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_sys.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_sys.set_defaults(func=cmd_system_status)
    ap_ui = parent.add_parser("ui-snapshot", help="Build UI snapshot bundle (read-only).")
    ap_ui.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ui.add_argument("--out", default=".cache/reports/ui_snapshot_bundle.v1.json", help="Output JSON path.")
    ap_ui.set_defaults(func=cmd_ui_snapshot)
    ap_ui_bundle = parent.add_parser("ui-snapshot-bundle", help="Build UI snapshot bundle (read-only).")
    ap_ui_bundle.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ui_bundle.add_argument("--out", default=".cache/reports/ui_snapshot_bundle.v1.json", help="Output JSON path.")
    ap_ui_bundle.set_defaults(func=cmd_ui_snapshot)

    ap_cockpit = parent.add_parser("cockpit-serve", help="Serve cockpit lite UI (local, no network).")
    ap_cockpit.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_cockpit.add_argument("--port", default="8787", help="Port (default: 8787).")
    ap_cockpit.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1).")
    ap_cockpit.set_defaults(func=cmd_cockpit_serve)

    ap_cockpit_hc = parent.add_parser("cockpit-healthcheck", help="Run cockpit lite healthcheck (local, no network).")
    ap_cockpit_hc.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_cockpit_hc.add_argument("--port", default="8787", help="Port (default: 8787).")
    ap_cockpit_hc.set_defaults(func=cmd_cockpit_healthcheck)

    register_planner_and_intake_subcommands(
        parent,
        cmd_planner_notes_create=cmd_planner_notes_create,
        cmd_planner_notes_delete=cmd_planner_notes_delete,
        cmd_preflight_stamp=cmd_preflight_stamp,
        cmd_work_item_lease_seed=cmd_work_item_lease_seed,
        cmd_doer_loop_lock_seed=cmd_doer_loop_lock_seed,
        cmd_doer_loop_lock_status=cmd_doer_loop_lock_status,
        cmd_doer_loop_lock_clear=cmd_doer_loop_lock_clear,
        cmd_work_intake_select=cmd_work_intake_select,
        cmd_work_intake_claim=cmd_work_intake_claim,
        cmd_work_intake_close=cmd_work_intake_close,
        cmd_work_intake_autoselect=cmd_work_intake_autoselect,
        cmd_doer_actionability=cmd_doer_actionability,
    )

    from src.ops.commands.extension_cmds import register_extension_subcommands as _register_extension

    _register_extension(parent)

    ap_int = parent.add_parser("integrity-verify", help="Run integrity verify (snapshot + verify-on-read).")
    ap_int.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_int.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_int.set_defaults(func=cmd_integrity_verify)

    ap_intake = parent.add_parser("work-intake-build", help="Build work intake from gaps + PDCA (workspace).")
    ap_intake.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake.set_defaults(func=cmd_work_intake_build)

    ap_intake_check = parent.add_parser("work-intake-check", help="Build + summarize work intake (program-led).")
    ap_intake_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_check.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_intake_check.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_intake_check.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_intake_check.set_defaults(func=cmd_work_intake_check)

    ap_intake_exec = parent.add_parser("work-intake-exec-ticket", help="Execute TICKET intake items (safe-only, workspace-only).")
    ap_intake_exec.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_exec.add_argument("--limit", default="3", help="Max items to execute (default: 3).")
    ap_intake_exec.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_intake_exec.set_defaults(func=cmd_work_intake_exec_ticket)

    ap_auto_loop = parent.add_parser(
        "auto-loop",
        help="Run decision inbox -> bulk apply -> doer loop (program-led, no-wait).",
    )
    ap_auto_loop.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_auto_loop.add_argument("--budget_seconds", required=True, help="Budget seconds (required).")
    ap_auto_loop.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_auto_loop.set_defaults(func=cmd_auto_loop)

    ap_decision_inbox = parent.add_parser(
        "decision-inbox-build",
        help="Build decision inbox from blocked items (program-led, workspace-only).",
    )
    ap_decision_inbox.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_decision_inbox.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_decision_inbox.set_defaults(func=cmd_decision_inbox_build)

    ap_decision_show = parent.add_parser(
        "decision-inbox-show",
        help="Show decision inbox summary (program-led, workspace-only).",
    )
    ap_decision_show.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_decision_show.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_decision_show.set_defaults(func=cmd_decision_inbox_show)

    ap_decision_apply = parent.add_parser(
        "decision-apply",
        help="Apply a decision (workspace-only, program-led).",
    )
    ap_decision_apply.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_decision_apply.add_argument("--decision-id", required=True, help="Decision id to apply.")
    ap_decision_apply.add_argument("--option-id", required=True, help="Option id to apply.")
    ap_decision_apply.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_decision_apply.set_defaults(func=cmd_decision_apply)

    ap_decision_bulk = parent.add_parser(
        "decision-apply-bulk",
        help="Apply decisions in bulk (workspace-only, program-led).",
    )
    ap_decision_bulk.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_decision_bulk.add_argument("--mode", default="safe_defaults", help="safe_defaults (default: safe_defaults).")
    ap_decision_bulk.add_argument("--decision-ids", default="", help="Comma-separated decision ids to apply.")
    ap_decision_bulk.set_defaults(func=cmd_decision_apply_bulk)

    ap_decision_seed = parent.add_parser(
        "decision-seed",
        help="Seed a deterministic decision item (workspace-only, program-led).",
    )
    ap_decision_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_decision_seed.add_argument("--kind", required=True, help="Decision kind (e.g., NETWORK_ENABLE).")
    ap_decision_seed.add_argument("--target", required=True, help="Decision target (string).")
    ap_decision_seed.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_decision_seed.set_defaults(func=cmd_decision_seed)

    ap_intake_link = parent.add_parser(
        "intake-link-report",
        help="Link REQ to intake items (workspace-only report + plan-only CHG).",
    )
    ap_intake_link.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_link.add_argument("--req-id", required=True, help="REQ id to match (e.g., REQ-YYYYMMDD-...).")
    ap_intake_link.add_argument("--write-plan", default="false", help="true|false (default: false).")
    ap_intake_link.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_intake_link.set_defaults(func=cmd_intake_link_report)

    register_context_subcommands(parent)
    ap_layer = parent.add_parser("layer-boundary-check", help="Check layer boundary constraints (report|strict).")
    ap_layer.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_layer.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_layer.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_layer.set_defaults(func=cmd_layer_boundary_check)

    ap_prom = parent.add_parser("promotion-bundle", help="Create promotion bundle from incubator (draft-only).")
    ap_prom.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_prom.add_argument("--mode", default="", help="customer_clean|internal_dev (default: policy).")
    ap_prom.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_prom.set_defaults(func=cmd_promotion_bundle)

    ap_hygiene = parent.add_parser("repo-hygiene", help="Repo hygiene report (warn-only, no auto-fix).")
    ap_hygiene.add_argument("--mode", default="report", help="report|suggest (default: report).")
    ap_hygiene.add_argument("--layout", default="docs/OPERATIONS/repo-layout.v1.json")
    ap_hygiene.add_argument("--out", default=".cache/repo_hygiene/report.json")
    ap_hygiene.set_defaults(func=cmd_repo_hygiene)

    ap_doc = parent.add_parser("doc-graph", help="Doc graph scan (workspace report, warn-only by default).")
    ap_doc.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doc.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_doc.add_argument("--out", default=".cache/reports/doc_graph_report.v1.json")
    ap_doc.set_defaults(func=cmd_doc_graph)

    ap_nav = parent.add_parser("doc-nav-check", help="Program-led doc nav check (doc-graph + system-status).")
    ap_nav.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_nav.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_nav.add_argument("--strict", default="false", help="true|false (default: false).")
    ap_nav.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_nav.set_defaults(func=cmd_doc_nav_check)

    ap_nav_start = parent.add_parser("doc-nav-job-start", help="Start doc nav check as background job.")
    ap_nav_start.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_nav_start.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_nav_start.add_argument("--strict", default="true", help="true|false (default: true).")
    ap_nav_start.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_nav_start.set_defaults(func=cmd_doc_nav_job_start)

    ap_nav_poll = parent.add_parser("doc-nav-job-poll", help="Poll doc nav job.")
    ap_nav_poll.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_nav_poll.add_argument("--job-id", required=True, help="Job id.")
    ap_nav_poll.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_nav_poll.set_defaults(func=cmd_doc_nav_job_poll)
