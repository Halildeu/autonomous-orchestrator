from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_extension_registry(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.ops.extension_registry import run_extension_registry

    res = run_extension_registry(workspace_root=ws, mode=mode, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_extension_help(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    detail = parse_reaper_bool(str(args.detail))
    chat = parse_reaper_bool(str(args.chat))

    from src.ops.extension_help import run_extension_help

    res = run_extension_help(workspace_root=ws, detail=detail, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_extension_run(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    extension_id = str(args.extension_id or "").strip()
    if not extension_id:
        warn("FAIL error=EXTENSION_ID_REQUIRED")
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.ops.extension_run import run_extension_run

    res = run_extension_run(workspace_root=ws, extension_id=extension_id, mode=mode, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_planner_build_plan(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    mode = str(args.mode or "plan_first").strip() or "plan_first"
    out = str(args.out or "latest").strip() or "latest"

    from src.prj_planner.planner_build import run_planner_build_plan

    payload = run_planner_build_plan(workspace_root=ws, mode=mode, out=out)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_planner_show_plan(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    plan_id = str(args.plan_id or "").strip() or None
    latest = parse_reaper_bool(str(args.latest))
    chat = parse_reaper_bool(str(args.chat))

    from src.prj_planner.planner_build import run_planner_show_plan

    payload = run_planner_show_plan(workspace_root=ws, plan_id=plan_id, latest=latest)
    if chat and isinstance(payload, dict):
        _emit_planner_show_plan_chat(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_planner_apply_selection(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    plan_id = str(args.plan_id or "").strip() or None
    latest = parse_reaper_bool(str(args.latest))

    from src.prj_planner.planner_build import run_planner_apply_selection

    payload = run_planner_apply_selection(workspace_root=ws, plan_id=plan_id, latest=latest)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_status(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    from src.prj_airunner.airunner_tick_admin import run_airunner_status

    payload = run_airunner_status(workspace_root=ws)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_lock_status(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    from src.prj_airunner.airunner_tick_admin import run_airunner_lock_status

    payload = run_airunner_lock_status(workspace_root=ws)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_lock_clear_stale(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    try:
        max_age = int(args.max_age_seconds)
    except Exception:
        warn("FAIL error=MAX_AGE_REQUIRED")
        return 2
    if max_age <= 0:
        warn("FAIL error=MAX_AGE_REQUIRED")
        return 2

    from src.prj_airunner.airunner_tick_admin import run_airunner_lock_clear_stale

    payload = run_airunner_lock_clear_stale(workspace_root=ws, max_age_seconds=max_age)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_run(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    ticks = 2
    try:
        ticks = int(args.ticks)
    except Exception:
        ticks = 2
    mode = str(args.mode or "no_wait")
    budget_seconds = 0
    try:
        budget_seconds = int(args.budget_seconds)
    except Exception:
        budget_seconds = 0
    force_active_hours = parse_reaper_bool(str(getattr(args, "force_active_hours", "false")))

    from src.prj_airunner.airunner_run import run_airunner_run

    payload = run_airunner_run(
        workspace_root=ws,
        ticks=ticks,
        mode=mode,
        budget_seconds=budget_seconds if budget_seconds > 0 else None,
        force_active_hours=force_active_hours,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_jobs_seed(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    kind = str(args.kind or "").strip()
    state = str(args.state or "").strip()
    try:
        count = int(args.count)
    except Exception:
        count = 1

    from src.prj_airunner.airunner_jobs import seed_jobs

    payload = seed_jobs(workspace_root=ws, kind=kind, state=state, count=count)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_baseline(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    from src.prj_airunner.airunner_run import run_airunner_baseline

    payload = run_airunner_baseline(workspace_root=ws)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_proof_bundle(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.prj_airunner.airunner_proof_bundle import run_airunner_proof_bundle

    payload = run_airunner_proof_bundle(workspace_root=ws)
    if chat and isinstance(payload, dict):
        _emit_airunner_proof_bundle_chat(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def _emit_airunner_chat(payload: dict[str, Any], *, title: str) -> None:
    evidence = []
    for key in ("report_path", "report_md_path", "heartbeat_path", "jobs_index_path", "watchdog_state_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    print("PREVIEW:")  # AUTOPILOT CHAT
    print(f"- {title} program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    print("ACTIONS:")
    print("- Check work-intake + system-status if status WARN/FAIL")
    print("NEXT:")
    print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _emit_airunner_proof_bundle_chat(payload: dict[str, Any]) -> None:
    evidence = []
    for key in ("report_path", "report_md_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    missing = payload.get("missing_inputs")
    missing_list = sorted([str(item) for item in missing if isinstance(item, str)]) if isinstance(missing, list) else []

    print("PREVIEW:")  # AUTOPILOT CHAT
    print("- airrunner-proof-bundle program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    if missing_list:
        print("ACTIONS:")
        print("- Missing inputs detected; run airunner-baseline, airunner-run, and seed/proof as needed")
    else:
        print("ACTIONS:")
        print("- Verify proof bundle via UI snapshot if needed")
    print("NEXT:")
    if missing_list:
        print("- Run seed/proof inputs / Durumu göster / Duraklat")
    else:
        print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _emit_planner_show_plan_chat(payload: dict[str, Any]) -> None:
    evidence = []
    for key in ("plan_path", "summary_path", "selection_path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            evidence.append(value)
    evidence = sorted(set(evidence))

    print("PREVIEW:")  # AUTOPILOT CHAT
    print("- planner-show-plan program-led run")
    print("RESULT:")
    print(f"- status={payload.get('status')}")
    if payload.get("error_code"):
        print(f"- error_code={payload.get('error_code')}")
    if payload.get("plan_id"):
        print(f"- plan_id={payload.get('plan_id')}")
    print("EVIDENCE:")
    if evidence:
        for path in evidence:
            print(f"- {path}")
    else:
        print("- (none)")
    print("ACTIONS:")
    if payload.get("status") == "IDLE":
        print("- Build a plan first or provide --plan-id")
    else:
        print("- Review plan steps + selection before apply")
    print("NEXT:")
    print("- Devam et / Durumu göster / Duraklat")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def cmd_airunner_tick(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.prj_airunner.airunner_tick import run_airunner_tick

    payload = run_airunner_tick(workspace_root=ws)
    if chat and isinstance(payload, dict):
        _emit_airunner_chat(payload, title="Airunner tick")
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_watchdog(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))
    from src.prj_airunner.airunner_tick_admin import run_airunner_watchdog

    payload = run_airunner_watchdog(workspace_root=ws)
    if chat and isinstance(payload, dict):
        _emit_airunner_chat(payload, title="Airunner watchdog")
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_release_plan(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    detail = parse_reaper_bool(str(args.detail))

    from src.prj_release_automation.release_engine import build_release_plan

    payload = build_release_plan(workspace_root=ws, channel=channel, detail=detail)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_release_prepare(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None

    from src.prj_release_automation.release_engine import prepare_release

    payload = prepare_release(workspace_root=ws, channel=channel)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_release_publish(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    allow_network = parse_reaper_bool(str(args.allow_network))
    trusted_context = parse_reaper_bool(str(args.trusted_context))

    from src.prj_release_automation.release_engine import publish_release

    payload = publish_release(
        workspace_root=ws,
        channel=channel,
        allow_network=allow_network,
        trusted_context=trusted_context,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE", "SKIP"} else 2


def cmd_release_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    channel = str(args.channel or "").strip().lower() or None
    chat = parse_reaper_bool(str(args.chat))

    from src.prj_release_automation.release_engine import run_release_check

    res = run_release_check(workspace_root=ws, channel=channel, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_github_ops_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.prj_github_ops.github_ops import run_github_ops_check

    res = run_github_ops_check(workspace_root=ws, chat=chat)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_github_ops_job_start(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    kind = str(args.kind or "").strip()
    if not kind:
        warn("FAIL error=KIND_REQUIRED")
        return 2

    dry_run = parse_reaper_bool(str(args.dry_run))

    from src.prj_github_ops.github_ops import start_github_ops_job

    payload = start_github_ops_job(workspace_root=ws, kind=kind, dry_run=dry_run)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "QUEUED", "RUNNING"} else 2


def cmd_github_ops_job_poll(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(args.job_id or "").strip()
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2

    from src.prj_github_ops.github_ops import poll_github_ops_job

    payload = poll_github_ops_job(workspace_root=ws, job_id=job_id)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE", "SKIP", "PASS", "RUNNING", "QUEUED"} else 2


def _resolve_workspace_root(args: argparse.Namespace) -> Path | None:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return None
    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return None
    return ws


def register_extension_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_ext = parent.add_parser("extension-registry", help="Build extension registry (workspace, program-led).")
    ap_ext.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_ext.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_ext.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_ext.set_defaults(func=cmd_extension_registry)

    ap_help = parent.add_parser("extension-help", help="Summarize extensions for humans + AI (program-led).")
    ap_help.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_help.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_help.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_help.set_defaults(func=cmd_extension_help)

    ap_run = parent.add_parser("extension-run", help="Run extension in isolated workspace (program-led).")
    ap_run.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_run.add_argument("--extension-id", required=True, help="Extension id.")
    ap_run.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_run.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_run.set_defaults(func=cmd_extension_run)

    ap_airunner_status = parent.add_parser("airunner-status", help="Airunner status (program-led).")
    ap_airunner_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_status.set_defaults(func=cmd_airunner_status)

    ap_airunner_lock_status = parent.add_parser("airunner-lock-status", help="Airunner lock status (program-led).")
    ap_airunner_lock_status.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_lock_status.set_defaults(func=cmd_airunner_lock_status)

    ap_airunner_lock_clear = parent.add_parser("airunner-lock-clear-stale", help="Clear stale airunner lock (program-led).")
    ap_airunner_lock_clear.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_lock_clear.add_argument("--max-age-seconds", required=True, help="Max heartbeat age in seconds.")
    ap_airunner_lock_clear.set_defaults(func=cmd_airunner_lock_clear_stale)

    ap_airunner_baseline = parent.add_parser("airunner-baseline", help="Airunner baseline snapshot (program-led).")
    ap_airunner_baseline.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_baseline.set_defaults(func=cmd_airunner_baseline)

    ap_airunner_proof = parent.add_parser("airunner-proof-bundle", help="Build airrunner proof bundle (program-led).")
    ap_airunner_proof.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_proof.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_proof.set_defaults(func=cmd_airunner_proof_bundle)

    ap_airunner_run = parent.add_parser("airunner-run", help="Airunner tick (program-led).")
    ap_airunner_run.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_run.add_argument("--ticks", default="2", help="Number of ticks (default: 2).")
    ap_airunner_run.add_argument("--mode", default="no_wait", help="no_wait (default: no_wait).")
    ap_airunner_run.add_argument("--budget-seconds", default="0", help="Budget seconds (default: 0=disabled).")
    ap_airunner_run.add_argument("--budget_seconds", dest="budget_seconds", default="0", help="Alias for --budget-seconds.")
    ap_airunner_run.add_argument(
        "--force-active-hours",
        default="false",
        help="true|false (default: false). Bypass active-hours gate for manual proof.",
    )
    ap_airunner_run.set_defaults(func=cmd_airunner_run)

    ap_airunner_seed = parent.add_parser("airunner-jobs-seed", help="Seed airunner jobs (workspace-only).")
    ap_airunner_seed.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_seed.add_argument("--kind", required=True, help="Job kind (SMOKE_FULL etc.).")
    ap_airunner_seed.add_argument("--state", default="queued", help="queued|running (default: queued).")
    ap_airunner_seed.add_argument("--count", default="1", help="Number of jobs to seed (default: 1).")
    ap_airunner_seed.set_defaults(func=cmd_airunner_jobs_seed)

    ap_airunner_tick = parent.add_parser("airunner-tick", help="Airunner tick (program-led, chat-aware).")
    ap_airunner_tick.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_tick.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_tick.set_defaults(func=cmd_airunner_tick)

    ap_airunner_watchdog = parent.add_parser("airunner-watchdog", help="Airunner watchdog (program-led).")
    ap_airunner_watchdog.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_airunner_watchdog.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_airunner_watchdog.set_defaults(func=cmd_airunner_watchdog)

    ap_plan = parent.add_parser("release-plan", help="Build release plan (workspace, program-led).")
    ap_plan.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_plan.add_argument("--channel", default="", help="rc|final (default: policy default).")
    ap_plan.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_plan.set_defaults(func=cmd_release_plan)

    ap_prepare = parent.add_parser("release-prepare", help="Prepare release manifest + notes (workspace).")
    ap_prepare.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_prepare.add_argument("--channel", default="", help="rc|final (default: plan channel).")
    ap_prepare.set_defaults(func=cmd_release_prepare)

    ap_publish = parent.add_parser("release-publish", help="Publish release (policy-gated, network off by default).")
    ap_publish.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_publish.add_argument("--channel", default="", help="rc|final (default: plan channel).")
    ap_publish.add_argument("--allow-network", default="false", help="true|false (default: false).")
    ap_publish.add_argument("--trusted-context", default="false", help="true|false (default: false).")
    ap_publish.set_defaults(func=cmd_release_publish)

    ap_check = parent.add_parser("release-check", help="Single gate: release plan + system + portfolio.")
    ap_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_check.add_argument("--channel", default="", help="rc|final (default: policy default).")
    ap_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_check.set_defaults(func=cmd_release_check)

    ap_gh_check = parent.add_parser("github-ops-check", help="GitHub ops check (program-led, local).")
    ap_gh_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_check.add_argument("--chat", default="true", help="true|false (default: true).")
    ap_gh_check.set_defaults(func=cmd_github_ops_check)

    ap_gh_start = parent.add_parser("github-ops-job-start", help="Start GitHub ops job (program-led).")
    ap_gh_start.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_start.add_argument(
        "--kind",
        required=True,
        help="Job kind (pr_list|pr_open|pr_update|merge|deploy_trigger|status_poll|PR_OPEN|PR_POLL|CI_POLL|MERGE|RELEASE_RC|RELEASE_FINAL).",
    )
    ap_gh_start.add_argument("--dry-run", default="true", help="true|false (default: true).")
    ap_gh_start.set_defaults(func=cmd_github_ops_job_start)

    ap_gh_poll = parent.add_parser("github-ops-job-poll", help="Poll GitHub ops job (program-led).")
    ap_gh_poll.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_gh_poll.add_argument("--job-id", required=True, help="Job id.")
    ap_gh_poll.set_defaults(func=cmd_github_ops_job_poll)
