from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.commands.extension_cmds_helpers_v2 import (
    _dump_json,
    _emit_airunner_chat,
    _emit_airunner_proof_bundle_chat,
    _emit_planner_show_plan_chat,
    _load_json,
    _now_compact,
    _resolve_workspace_root,
)
from src.ops.reaper import parse_bool as parse_reaper_bool

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - zoneinfo missing fallback
    ZoneInfo = None

def _parse_hhmm(raw: str) -> tuple[str | None, str | None]:
    value = str(raw or "").strip()
    if not value:
        return None, "MISSING"
    if not re.match(r"^[0-2][0-9]:[0-5][0-9]$", value):
        return None, "FORMAT"
    hour = int(value.split(":", 1)[0])
    minute = int(value.split(":", 1)[1])
    if hour > 23 or minute > 59:
        return None, "RANGE"
    return f"{hour:02d}:{minute:02d}", None


def _now_local_hhmm(tz_name: str) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    tz_label = tz_name or "Europe/Istanbul"
    now_utc = datetime.now(timezone.utc)
    if ZoneInfo is None:
        notes.append("tz_fallback=UTC")
        tz_label = "UTC"
        now_local = now_utc
    else:
        try:
            now_local = now_utc.astimezone(ZoneInfo(tz_label))
        except Exception:
            notes.append("tz_invalid_fallback=UTC")
            tz_label = "UTC"
            now_local = now_utc
    return now_local.strftime("%H:%M"), tz_label, notes


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


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


def cmd_north_star_subject_to_plan(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    subject_id = str(getattr(args, "subject_id", "") or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2

    mode = str(getattr(args, "mode", "plan_first") or "plan_first").strip() or "plan_first"
    out = str(getattr(args, "out", "latest") or "latest").strip() or "latest"

    from src.prj_planner.north_star_subject_plan import run_north_star_subject_to_plan

    payload = run_north_star_subject_to_plan(workspace_root=ws, subject_id=subject_id, mode=mode, out=out)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_north_star_subject_plan_profile_run(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    subject_id = str(getattr(args, "subject_id", "") or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2

    profile = str(getattr(args, "profile", "C") or "C").strip() or "C"
    run_set = str(getattr(args, "run_set", "abc") or "abc").strip() or "abc"
    mode = str(getattr(args, "mode", "plan_first") or "plan_first").strip() or "plan_first"
    out = str(getattr(args, "out", "latest") or "latest").strip() or "latest"
    persist_profile = parse_reaper_bool(str(getattr(args, "persist_profile", "true")))

    from src.prj_planner.north_star_subject_plan_profile_run import run_north_star_subject_plan_profile_run

    payload = run_north_star_subject_plan_profile_run(
        workspace_root=ws,
        subject_id=subject_id,
        profile=profile,
        run_set=run_set,
        mode=mode,
        out=out,
        persist_profile=persist_profile,
    )
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


def cmd_airunner_active_hours_set(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    end_raw = str(getattr(args, "end", "") or "").strip()
    start_raw = str(getattr(args, "start", "") or "").strip()
    tz_name = str(getattr(args, "tz", "") or "").strip() or "Europe/Istanbul"
    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    if not end_raw:
        warn("FAIL error=END_REQUIRED")
        return 2
    end_val, end_err = _parse_hhmm(end_raw)
    if end_err:
        warn("FAIL error=END_INVALID")
        return 2

    tz_notes: list[str] = []
    if start_raw:
        start_val, start_err = _parse_hhmm(start_raw)
        if start_err:
            warn("FAIL error=START_INVALID")
            return 2
        start_source = "explicit"
        tz_label = tz_name
    else:
        start_val, tz_label, tz_notes = _now_local_hhmm(tz_name)
        start_source = "default_now"

    core_path = repo_root() / "policies" / "policy_airunner.v1.json"
    override_path = ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    base: dict[str, Any] = {}
    if core_path.exists():
        try:
            base = _load_json(core_path)
        except Exception:
            base = {}
    override: dict[str, Any] = {}
    if override_path.exists():
        try:
            override = _load_json(override_path)
        except Exception:
            override = {}
    policy = _deep_merge(base if isinstance(base, dict) else {}, override if isinstance(override, dict) else {})

    policy["enabled"] = True
    schedule = policy.get("schedule") if isinstance(policy.get("schedule"), dict) else {}
    active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
    active_hours.update({"enabled": True, "tz": tz_label, "start": start_val, "end": end_val})
    schedule["active_hours"] = active_hours
    if "outside_hours_mode" not in schedule:
        schedule["outside_hours_mode"] = "poll_only"
    policy["schedule"] = schedule

    notes = policy.get("notes") if isinstance(policy.get("notes"), list) else []
    notes = [str(n) for n in notes if str(n)]
    notes.extend(
        [
            "PROGRAM_LED=true",
            "active_hours_set=true",
            f"active_hours_start_source={start_source}",
        ]
    )
    notes.extend(tz_notes)
    policy["notes"] = sorted({n for n in notes if n})

    backup_path: Path | None = None
    if override_path.exists():
        ts = _now_compact()
        backup_path = override_path.parent / f"{override_path.name}.bak.{ts}"
        backup_path.write_text(override_path.read_text(encoding="utf-8"), encoding="utf-8")
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(_dump_json(policy), encoding="utf-8")

    report_path = ws / ".cache" / "reports" / "airunner_active_hours_set.v1.json"
    report_payload = {
        "status": "OK",
        "override_path": str(Path(".cache") / "policy_overrides" / "policy_airunner.override.v1.json"),
        "backup_path": str(backup_path.relative_to(ws)) if isinstance(backup_path, Path) else None,
        "start": start_val,
        "end": end_val,
        "tz": tz_label,
        "start_source": start_source,
        "notes": ["PROGRAM_LED=true"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report_payload), encoding="utf-8")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: airrunner-active-hours-set (workspace-only)")
        print(f"workspace_root={ws}")
        print("RESULT:")
        print(f"status=OK start={start_val} end={end_val} tz={tz_label}")
        print("EVIDENCE:")
        print(str(report_payload.get("override_path")))
        if report_payload.get("backup_path"):
            print(str(report_payload.get("backup_path")))
        print(str(Path(".cache") / "reports" / "airunner_active_hours_set.v1.json"))
        print("ACTIONS:")
        print("airrunner-status / airrunner-run")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(report_payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_airunner_auto_run_start(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    stop_at = str(getattr(args, "stop_at", "") or "").strip()
    timezone_name = str(getattr(args, "timezone", "") or "").strip()
    mode = str(getattr(args, "mode", "") or "").strip()
    job_kind = str(getattr(args, "job_kind", "") or "").strip()
    dry_run = parse_reaper_bool(str(getattr(args, "dry_run", "false")))
    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    from src.prj_airunner.airunner_auto_run_job import start_auto_run

    payload = start_auto_run(
        workspace_root=ws,
        stop_at_local=stop_at or None,
        timezone_name=timezone_name or None,
        mode=mode or None,
        job_kind=job_kind or None,
        dry_run=dry_run,
    )
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: airunner-auto-run-start (no-wait)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} job_id={payload.get('job_id')} job_status={payload.get('job_status')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [payload.get("job_path"), payload.get("jobs_index_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("airunner-auto-run-poll")
        print("system-status")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_auto_run_poll(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    job_id = str(getattr(args, "job_id", "") or "").strip()
    max_polls = 1
    try:
        max_polls = int(getattr(args, "max", 1))
    except Exception:
        max_polls = 1
    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))

    from src.prj_airunner.airunner_auto_run_job import poll_auto_run

    payload = poll_auto_run(workspace_root=ws, job_id=job_id, max_polls=max_polls)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: airunner-auto-run-poll (no-wait)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} job_id={payload.get('job_id')} job_status={payload.get('job_status')}")
        if payload.get("error_code"):
            print(f"error_code={payload.get('error_code')}")
        print("EVIDENCE:")
        for p in [
            payload.get("job_path"),
            payload.get("jobs_index_path"),
            payload.get("last_poll_path"),
        ]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("airunner-auto-run-poll")
        print("system-status")
        print("ui-snapshot-bundle")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_airunner_auto_run_check(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2

    chat = parse_reaper_bool(str(getattr(args, "chat", "false")))
    from src.prj_airunner.airunner_auto_run_job import check_auto_run

    payload = check_auto_run(workspace_root=ws)
    status = payload.get("status") if isinstance(payload, dict) else "WARN"

    if chat and isinstance(payload, dict):
        print("PREVIEW:")
        print("PROGRAM-LED: airunner-auto-run-check (read-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={payload.get('status')} job_id={payload.get('job_id')} job_status={payload.get('job_status')}")
        print("EVIDENCE:")
        for p in [payload.get("jobs_index_path"), payload.get("last_poll_path"), payload.get("last_closeout_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        print("airunner-auto-run-start")
        print("airunner-auto-run-poll")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


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
