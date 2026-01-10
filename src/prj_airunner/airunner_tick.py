from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from src.ops.commands.maintenance_cmds import (
    cmd_system_status,
    cmd_ui_snapshot,
    cmd_work_intake_autoselect,
    cmd_work_intake_check,
    cmd_work_intake_exec_ticket,
)
from src.ops.commands.extension_cmds import (
    cmd_github_ops_job_poll,
    cmd_github_ops_job_start,
    cmd_release_check,
)
from src.ops.work_intake_from_sources import _load_autopilot_policy
from src.ops.roadmap_cli import cmd_portfolio_status
from src.prj_airunner.airunner_jobs import load_jobs_policy, update_jobs
from src.prj_airunner.airunner_time_sinks import build_time_sinks_report
from src.prj_airunner.airunner_tick_utils import (
    _active_hours_snapshot,
    _heartbeat_age_seconds,
    _load_heartbeat,
    _load_json,
    _load_lock,
    _lock_is_stale,
    _lock_paths,
    _now_iso,
    _parse_iso,
    _rel_to_workspace,
    _release_lock,
    _run_cmd_json,
    _run_cmd_json_with_perf,
    _runtime_day,
    _load_runtime_state,
    _write_runtime_state,
    _write_heartbeat,
    _write_lock,
)
from src.prj_airunner.airunner_tick_support import (
    _emit_idle_tick,
    _load_policy,
    _repo_root,
    _run_fast_gate,
    _write_tick_report,
)
from src.prj_airunner.airunner_tick_helpers import (
    _allow_repeat_tick,
    _canonical_json,
    _compute_tick_id,
    _hash_text,
    _intake_suggests_extension,
    _load_airunner_jobs_running,
    _load_github_ops_jobs_index,
    _window_bucket,
    _work_intake_hash,
)
from src.prj_airunner.auto_mode_dispatch import (
    auto_mode_network_allowed,
    load_auto_mode_policy,
    plan_auto_mode_dispatch,
    write_plan_only,
    write_selection_file,
)
def run_airunner_tick(*, workspace_root: Path, force_active_hours: bool = False) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    enabled = bool(policy.get("enabled", False))
    schedule = policy.get("schedule") if isinstance(policy.get("schedule"), dict) else {}
    schedule_mode = str(schedule.get("mode") or "OFF")
    watchdog = policy.get("watchdog") if isinstance(policy.get("watchdog"), dict) else {}
    job_policy = policy.get("job_policy") if isinstance(policy.get("job_policy"), dict) else {}
    core_root = _repo_root()
    now = datetime.now(timezone.utc)
    required_ops = [
        "work-intake-check",
        "work-intake-exec-ticket",
        "system-status",
        "portfolio-status",
        "ui-snapshot-bundle",
    ]
    allowed_ops = policy.get("single_gate", {}).get("allowed_ops") if isinstance(policy.get("single_gate"), dict) else []
    allowed_ops = [str(x) for x in allowed_ops if isinstance(x, str)]
    if "ui-snapshot" in allowed_ops and "ui-snapshot-bundle" not in allowed_ops:
        allowed_ops.append("ui-snapshot-bundle")
    active_snapshot = _active_hours_snapshot(schedule, now)
    active_hours_enabled = bool(active_snapshot.get("active_hours_enabled", False))
    outside_hours_mode_effective = str(active_snapshot.get("outside_hours_mode_effective") or "poll_only")
    inside_hours_raw = bool(active_snapshot.get("inside_active_hours", True))
    inside_hours_effective = inside_hours_raw
    schedule_notes = list(active_snapshot.get("notes") or [])
    if outside_hours_mode_effective == "ignore":
        inside_hours_effective = True
        schedule_notes.append("outside_hours_mode_ignore")
    if force_active_hours:
        inside_hours_effective = True
        active_snapshot["inside_active_hours"] = True
        schedule_notes.append("force_active_hours=true")
    notes.extend(schedule_notes)
    def _active_meta(reason: str) -> dict[str, Any]:
        return {
            "active_hours_enabled": bool(active_hours_enabled),
            "active_hours_tz": str(active_snapshot.get("active_hours_tz") or ""),
            "now_local_hhmm": str(active_snapshot.get("now_local_hhmm") or ""),
            "inside_active_hours": bool(inside_hours_raw),
            "inside_active_hours_effective": bool(inside_hours_effective),
            "outside_hours_mode_effective": str(outside_hours_mode_effective),
            "gate_reason": reason,
        }
    outside_hours = bool(active_hours_enabled) and not inside_hours_effective and outside_hours_mode_effective != "ignore"
    if not enabled:
        return _emit_idle_tick(
            workspace_root=workspace_root,
            policy_source=policy_source,
            policy_hash=policy_hash,
            notes=notes,
            error_code="POLICY_DISABLED",
            tick_id_seed={"enabled": False, "policy_hash": policy_hash},
            active_meta=_active_meta("POLICY_DISABLED"),
        )
    if schedule_mode == "OFF":
        return _emit_idle_tick(
            workspace_root=workspace_root,
            policy_source=policy_source,
            policy_hash=policy_hash,
            notes=notes,
            error_code="SCHEDULE_OFF",
            tick_id_seed={"schedule": schedule_mode, "policy_hash": policy_hash},
            active_meta=_active_meta("SCHEDULE_OFF"),
        )
    missing_ops = [op for op in required_ops if op not in allowed_ops]
    if missing_ops and not outside_hours:
        return _emit_idle_tick(
            workspace_root=workspace_root,
            policy_source=policy_source,
            policy_hash=policy_hash,
            notes=notes,
            error_code="ALLOWED_OPS_MISSING",
            tick_id_seed={"missing_ops": missing_ops, "policy_hash": policy_hash},
            active_meta=_active_meta("ALLOWED_OPS_MISSING"),
            extra_notes=[f"missing_op={op}" for op in missing_ops],
        )
    runtime_day, runtime_notes = _runtime_day(schedule, now)
    notes.extend(runtime_notes)
    runtime_state = _load_runtime_state(workspace_root)
    runtime_used = 0
    if isinstance(runtime_state.get("date"), str) and runtime_state.get("date") == runtime_day:
        runtime_used = int(runtime_state.get("runtime_seconds", 0) or 0)
    max_runtime = int(policy.get("max_runtime_seconds_per_day", 0) or 0)
    if max_runtime and runtime_used >= max_runtime:
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": "WARN",
            "error_code": "RUNTIME_BUDGET_EXCEEDED",
            "tick_id": _hash_text(_canonical_json({"runtime_budget": True, "policy_hash": policy_hash})),
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        report.update(_active_meta("RUNTIME_BUDGET_EXCEEDED"))
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": "WARN",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }
    jobs_policy, jobs_policy_hash, jobs_notes = load_jobs_policy(core_root=core_root, workspace_root=workspace_root)
    perf_cfg = jobs_policy.get("perf") if isinstance(jobs_policy.get("perf"), dict) else {}
    notes.extend(jobs_notes)
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    autopilot_policy, _, autopilot_notes = _load_autopilot_policy(
        core_root=_repo_root(), workspace_root=workspace_root
    )
    notes.extend(autopilot_notes)
    autopilot_defaults = (
        autopilot_policy.get("defaults") if isinstance(autopilot_policy.get("defaults"), dict) else {}
    )
    auto_select_cfg = (
        autopilot_policy.get("auto_select") if isinstance(autopilot_policy.get("auto_select"), dict) else {}
    )
    auto_select_enabled = bool(auto_select_cfg.get("enabled", False))
    auto_mode_policy, auto_mode_source, auto_mode_hash, auto_mode_notes = load_auto_mode_policy(
        workspace_root=workspace_root
    )
    notes.extend(auto_mode_notes)
    auto_mode_enabled = bool(auto_mode_policy.get("enabled", False))
    auto_mode_mode = str(auto_mode_policy.get("mode") or "")
    auto_mode_limits = auto_mode_policy.get("limits") if isinstance(auto_mode_policy.get("limits"), dict) else {}
    max_actions = int(limits.get("max_actions_per_tick", 1)) if isinstance(limits.get("max_actions_per_tick"), int) else 1
    max_plans = int(limits.get("max_plans_per_tick", 1)) if isinstance(limits.get("max_plans_per_tick"), int) else 1
    if isinstance(autopilot_defaults.get("max_apply_per_tick"), int):
        max_actions = int(autopilot_defaults.get("max_apply_per_tick"))
    if isinstance(autopilot_defaults.get("max_plans_per_tick"), int):
        max_plans = int(autopilot_defaults.get("max_plans_per_tick"))
    max_poll = 1
    if isinstance(autopilot_defaults.get("max_poll_per_tick"), int):
        max_poll = max(1, int(autopilot_defaults.get("max_poll_per_tick")))
    max_dispatch_actions = int(auto_mode_limits.get("max_actions_per_tick", max_actions) or max_actions)
    max_dispatch_jobs = int(auto_mode_limits.get("max_jobs_start_per_tick", 1) or 1)
    auto_select_limit = auto_select_cfg.get("max_select")
    if isinstance(auto_select_limit, int) and auto_select_limit > 0:
        auto_select_limit = int(auto_select_limit)
    else:
        auto_select_limit = max_actions
    lock_ttl = int(policy.get("lock_ttl_seconds", 900) or 900)
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    lock = _load_lock(lock_path)
    force_poll_only = False
    if lock:
        if _lock_is_stale(lock, now):
            watchdog_action = str(watchdog.get("action") or "")
            if watchdog_action == "CLEAR_STALE_LOCK_THEN_POLL_ONLY":
                force_poll_only = True
                notes.append("STALE_LOCK_CLEARED")
            _release_lock(lock_path)
        else:
            report = {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": "IDLE",
                "error_code": "LOCKED",
                "tick_id": _hash_text(_canonical_json({"locked": True, "policy_hash": policy_hash})),
                "workspace_root": str(workspace_root),
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "ops_called": [],
                "actions": {"applied": 0, "planned": 0, "idle": 0},
                "evidence_paths": [str(Path(".cache") / "airunner" / "airunner_lock.v1.json")],
                "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
            }
            report.update(_active_meta("LOCKED"))
            rel_json, rel_md = _write_tick_report(report, workspace_root)
            return {
                "status": "IDLE",
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "report_path": rel_json,
                "report_md_path": rel_md,
            }
    lock_id = _hash_text(f"{workspace_root}:{now.isoformat()}:{policy_hash}")
    _write_lock(lock_path, lock_id=lock_id, now=now, ttl_seconds=lock_ttl, workspace_root=workspace_root)
    tick_started_at = time.monotonic()
    ops_called: list[str] = []
    evidence_paths: list[str] = []
    error_code = None
    status = "OK"
    work_intake_hash = _work_intake_hash(workspace_root)
    window_bucket = _window_bucket(schedule)
    tick_id = _compute_tick_id(policy_hash, work_intake_hash, window_bucket)
    heartbeat = _load_heartbeat(heartbeat_path)
    last_tick_id = heartbeat.get("last_tick_id") if isinstance(heartbeat, dict) else None
    running_jobs = _load_airunner_jobs_running(workspace_root)
    if (
        isinstance(last_tick_id, str)
        and last_tick_id == tick_id
        and not running_jobs
        and not _allow_repeat_tick(workspace_root, allowed_ops)
    ):
        status = "IDLE"
        error_code = "NOOP_SAME_TICK"
        heartbeat_rel = _write_heartbeat(
            heartbeat_path,
            workspace_root=workspace_root,
            tick_id=tick_id,
            status=status,
            error_code=error_code,
            window_bucket=window_bucket,
            policy_hash=policy_hash,
            notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
        )
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": status,
            "error_code": error_code,
            "tick_id": tick_id,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [heartbeat_rel],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        report.update(_active_meta("NOOP_SAME_TICK"))
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        _release_lock(lock_path)
        return {
            "status": status,
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }
    try:
        fast_gate = _run_fast_gate(workspace_root)
        preflight_overall = str(fast_gate.get("preflight_overall") or "")
        if not preflight_overall:
            preflight_overall = (
                "PASS"
                if fast_gate.get("validate_schemas") == "PASS"
                and fast_gate.get("smoke_fast") == "PASS"
                and (fast_gate.get("script_budget") == "PASS" or int(fast_gate.get("hard_exceeded", 0) or 0) == 0)
                else "FAIL"
            )
        preflight_reason = str(fast_gate.get("preflight_reason") or "")
        if not preflight_reason:
            if preflight_overall == "PASS":
                preflight_reason = "NORMAL_FLOW"
            elif preflight_overall == "MISSING":
                preflight_reason = "PRECHECK_REQUIRED"
            elif preflight_overall == "STALE":
                preflight_reason = "PRECHECK_STALE"
            else:
                preflight_reason = "PRECHECK_FAILED"
        require_pass_for_apply = bool(fast_gate.get("require_pass_for_apply", True))
        allow_apply = preflight_overall == "PASS" or not require_pass_for_apply
        preflight_stamp_path = str(
            fast_gate.get("preflight_stamp_path") or fast_gate.get("report_path") or ""
        )
        preflight_meta = {
            "preflight_stamp_path": preflight_stamp_path or None,
            "preflight_overall": preflight_overall,
            "preflight_reason": preflight_reason,
        }
        if preflight_stamp_path:
            evidence_paths.append(preflight_stamp_path)
        if not allow_apply:
            notes.append(f"preflight_gate={preflight_reason}")
            if status == "OK":
                status = "WARN"
                error_code = preflight_reason
        if outside_hours:
            force_poll_only = bool(running_jobs)
        poll_only = bool(running_jobs) or force_poll_only
        jobs_index, _, job_stats = update_jobs(
            workspace_root=workspace_root,
            tick_id=tick_id,
            policy_hash=jobs_policy_hash,
            policy=jobs_policy,
            lifecycle_policy=job_policy,
            allow_enqueue=allow_apply and not poll_only and not outside_hours,
            poll_only=poll_only,
        )
        jobs_index_path = str(Path(".cache") / "airunner" / "jobs_index.v1.json")
        evidence_paths.append(jobs_index_path)
        queued_before = int(job_stats.get("queued_before", 0) or 0)
        running_before = int(job_stats.get("running_before", 0) or 0)
        queued_after = int(job_stats.get("queued_after", queued_before) or 0)
        running_after = int(job_stats.get("running_after", running_before) or 0)
        poll_only = poll_only or (queued_before + running_before) > 0
        outside_hours_no_airunner_jobs = outside_hours and (queued_before + running_before) == 0
        if poll_only and (force_poll_only or (queued_after + running_after) > 0):
            ui_payload = _run_cmd_json_with_perf(
                op_name="ui-snapshot-bundle",
                func=cmd_ui_snapshot,
                args=argparse.Namespace(
                    workspace_root=str(workspace_root),
                    out=".cache/reports/ui_snapshot_bundle.v1.json",
                ),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ui_report = ui_payload.get("report_path") if isinstance(ui_payload, dict) else None
            if isinstance(ui_report, str) and ui_report:
                evidence_paths.append(ui_report)
            heartbeat_rel = _write_heartbeat(
                heartbeat_path,
                workspace_root=workspace_root,
                tick_id=tick_id,
                status="OK",
                error_code=None,
                window_bucket=window_bucket,
                policy_hash=policy_hash,
                notes=notes + ["PROGRAM_LED=true", "NETWORK=false", "POLL_ONLY=true"],
            )
            evidence_paths.append(heartbeat_rel)
            report = {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": "OK",
                "error_code": None,
                "tick_id": tick_id,
                "workspace_root": str(workspace_root),
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "fast_gate": fast_gate,
                "jobs_started": int(job_stats.get("started", 0)),
                "jobs_polled": int(job_stats.get("polled", 0)),
                "jobs_running": int(job_stats.get("running", 0)),
                "jobs_failed": int(job_stats.get("failed", 0)),
                "jobs_passed": int(job_stats.get("passed", 0)),
                "queued_before": queued_before,
                "running_before": running_before,
                "queued_after": queued_after,
                "running_after": running_after,
                "jobs_archived_delta": int(job_stats.get("archived", 0)),
                "jobs_skipped_delta": int(job_stats.get("skipped", 0)),
                "poll_first_enforced": True,
                "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                "ops_called": ["airunner-jobs-poll", "ui-snapshot-bundle"],
                "actions": {"applied": 0, "planned": 0, "idle": 0},
                "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false", "POLL_ONLY=true"],
            }
            report.update(preflight_meta)
            report.update(
                _active_meta(
                    "OUTSIDE_ACTIVE_HOURS_POLL_ONLY" if outside_hours else "POLL_ONLY"
                )
            )
            rel_json, rel_md = _write_tick_report(report, workspace_root)
            return {
                "status": "OK",
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "report_path": rel_json,
                "report_md_path": rel_md,
                "jobs_started": int(job_stats.get("started", 0)),
                "jobs_polled": int(job_stats.get("polled", 0)),
                "jobs_running": int(job_stats.get("running", 0)),
                "jobs_failed": int(job_stats.get("failed", 0)),
                "jobs_passed": int(job_stats.get("passed", 0)),
                "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
            }
        if poll_only and (queued_after + running_after) == 0 and not force_poll_only:
            notes.append("POLL_CLEARED_CONTINUE")
            ops_called.append("airunner-jobs-poll")
        github_jobs = _load_github_ops_jobs_index(workspace_root)
        github_running = [
            j
            for j in github_jobs
            if str(j.get("status") or "") in {"QUEUED", "RUNNING"} and str(j.get("job_id") or "")
        ]
        github_queued_before = len([j for j in github_jobs if str(j.get("status") or "") == "QUEUED"])
        github_running_before = len([j for j in github_jobs if str(j.get("status") or "") == "RUNNING"])
        can_poll_github = "github-ops-job-poll" in allowed_ops
        can_start_github = "github-ops-job-start" in allowed_ops
        if can_poll_github and github_running:
            for job in github_running[:max_poll]:
                poll_payload = _run_cmd_json_with_perf(
                    op_name="github-ops-job-poll",
                    func=cmd_github_ops_job_poll,
                    args=argparse.Namespace(workspace_root=str(workspace_root), job_id=str(job.get("job_id"))),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ops_called.append("github-ops-job-poll")
                report_path = poll_payload.get("job_report_path") if isinstance(poll_payload, dict) else None
                if isinstance(report_path, str) and report_path:
                    evidence_paths.append(report_path)
                index_path = poll_payload.get("jobs_index_path") if isinstance(poll_payload, dict) else None
                if isinstance(index_path, str) and index_path:
                    evidence_paths.append(index_path)
            github_after = _load_github_ops_jobs_index(workspace_root)
            github_queued_after = len([j for j in github_after if str(j.get("status") or "") == "QUEUED"])
            github_running_after = len([j for j in github_after if str(j.get("status") or "") == "RUNNING"])
            if (github_queued_after + github_running_after) > 0:
                ui_payload = _run_cmd_json_with_perf(
                    op_name="ui-snapshot-bundle",
                    func=cmd_ui_snapshot,
                    args=argparse.Namespace(
                        workspace_root=str(workspace_root),
                        out=".cache/reports/ui_snapshot_bundle.v1.json",
                    ),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ui_report = ui_payload.get("report_path") if isinstance(ui_payload, dict) else None
                if isinstance(ui_report, str) and ui_report:
                    evidence_paths.append(ui_report)
                heartbeat_rel = _write_heartbeat(
                    heartbeat_path,
                    workspace_root=workspace_root,
                    tick_id=tick_id,
                    status="OK",
                    error_code=None,
                    window_bucket=window_bucket,
                    policy_hash=policy_hash,
                    notes=notes + ["PROGRAM_LED=true", "NETWORK=false", "POLL_ONLY=true", "GITHUB_POLL=true"],
                )
                evidence_paths.append(heartbeat_rel)
                report = {
                    "version": "v1",
                    "generated_at": _now_iso(),
                    "status": "OK",
                    "error_code": None,
                    "tick_id": tick_id,
                    "workspace_root": str(workspace_root),
                    "policy_source": policy_source,
                    "policy_hash": policy_hash,
                    "fast_gate": fast_gate,
                    "jobs_started": int(job_stats.get("started", 0)),
                    "jobs_polled": int(job_stats.get("polled", 0)) + 1,
                    "jobs_running": int(job_stats.get("running", 0)),
                    "jobs_failed": int(job_stats.get("failed", 0)),
                    "jobs_passed": int(job_stats.get("passed", 0)),
                    "jobs_archived_delta": int(job_stats.get("archived", 0)),
                    "jobs_skipped_delta": int(job_stats.get("skipped", 0)),
                    "poll_first_enforced": False,
                    "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                    "queued_before": queued_before,
                    "running_before": running_before,
                    "queued_after": queued_after,
                    "running_after": running_after,
                    "github_queued_before": github_queued_before,
                    "github_running_before": github_running_before,
                    "github_queued_after": github_queued_after,
                    "github_running_after": github_running_after,
                    "ops_called": ["github-ops-job-poll", "ui-snapshot-bundle"],
                    "actions": {"applied": 0, "planned": 0, "idle": 0},
                    "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                    "notes": notes
                    + [
                        "PROGRAM_LED=true",
                        "STRICT_ISOLATED=true",
                        "NETWORK=false",
                        "POLL_ONLY=true",
                        "GITHUB_POLL=true",
                    ],
                }
                report.update(preflight_meta)
                report.update(_active_meta("GITHUB_POLL_ONLY"))
                rel_json, rel_md = _write_tick_report(report, workspace_root)
                return {
                    "status": "OK",
                    "policy_source": policy_source,
                    "policy_hash": policy_hash,
                    "report_path": rel_json,
                    "report_md_path": rel_md,
                    "jobs_started": int(job_stats.get("started", 0)),
                    "jobs_polled": int(job_stats.get("polled", 0)) + 1,
                    "jobs_running": int(job_stats.get("running", 0)),
                    "jobs_failed": int(job_stats.get("failed", 0)),
                    "jobs_passed": int(job_stats.get("passed", 0)),
                    "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                }
            notes.append("GITHUB_POLL_CLEARED")
        if outside_hours and not force_active_hours:
            heartbeat_rel = _write_heartbeat(
                heartbeat_path,
                workspace_root=workspace_root,
                tick_id=tick_id,
                status="IDLE",
                error_code="OUTSIDE_ACTIVE_HOURS",
                window_bucket=window_bucket,
                policy_hash=policy_hash,
                notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
            )
            evidence_paths.append(heartbeat_rel)
            report = {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": "IDLE",
                "error_code": "OUTSIDE_ACTIVE_HOURS",
                "tick_id": tick_id,
                "workspace_root": str(workspace_root),
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "fast_gate": fast_gate,
                "jobs_started": int(job_stats.get("started", 0)),
                "jobs_polled": int(job_stats.get("polled", 0)),
                "jobs_running": int(job_stats.get("running", 0)),
                "jobs_failed": int(job_stats.get("failed", 0)),
                "jobs_passed": int(job_stats.get("passed", 0)),
                "jobs_archived_delta": int(job_stats.get("archived", 0)),
                "jobs_skipped_delta": int(job_stats.get("skipped", 0)),
                "poll_first_enforced": False,
                "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                "queued_before": queued_before,
                "running_before": running_before,
                "queued_after": queued_after,
                "running_after": running_after,
                "github_queued_before": github_queued_before,
                "github_running_before": github_running_before,
                "github_queued_after": github_queued_before,
                "github_running_after": github_running_before,
                "ops_called": [],
                "actions": {"applied": 0, "planned": 0, "idle": 0},
                "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
            }
            report.update(preflight_meta)
            report.update(_active_meta("OUTSIDE_ACTIVE_HOURS_IDLE"))
            rel_json, rel_md = _write_tick_report(report, workspace_root)
            _release_lock(lock_path)
            return {
                "status": "IDLE",
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "report_path": rel_json,
                "report_md_path": rel_md,
            }
        work_intake_payload = _run_cmd_json_with_perf(
            op_name="work-intake-check",
            func=cmd_work_intake_check,
            args=argparse.Namespace(workspace_root=str(workspace_root), mode="strict", chat="false", detail="false"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("work-intake-check")
        work_intake_path = work_intake_payload.get("work_intake_path") if isinstance(work_intake_payload, dict) else None
        if isinstance(work_intake_path, str) and work_intake_path:
            evidence_paths.append(work_intake_path)
        if auto_select_enabled and allow_apply:
            if "work-intake-autoselect" not in allowed_ops:
                status = "IDLE"
                error_code = "ALLOWED_OPS_MISSING"
                heartbeat_rel = _write_heartbeat(
                    heartbeat_path,
                    workspace_root=workspace_root,
                    tick_id=tick_id,
                    status=status,
                    error_code=error_code,
                    window_bucket=window_bucket,
                    policy_hash=policy_hash,
                    notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
                )
                evidence_paths.append(heartbeat_rel)
                report = {
                    "version": "v1",
                    "generated_at": _now_iso(),
                    "status": status,
                    "error_code": error_code,
                    "tick_id": tick_id,
                    "workspace_root": str(workspace_root),
                    "policy_source": policy_source,
                    "policy_hash": policy_hash,
                    "fast_gate": fast_gate,
                    "jobs_started": int(job_stats.get("started", 0)),
                    "jobs_polled": int(job_stats.get("polled", 0)),
                    "jobs_running": int(job_stats.get("running", 0)),
                    "jobs_failed": int(job_stats.get("failed", 0)),
                    "jobs_passed": int(job_stats.get("passed", 0)),
                    "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                    "ops_called": ["work-intake-check"],
                    "actions": {"applied": 0, "planned": 0, "idle": 0},
                    "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                    "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
                }
                report.update(preflight_meta)
                report.update(_active_meta("ALLOWED_OPS_MISSING"))
                rel_json, rel_md = _write_tick_report(report, workspace_root)
                _release_lock(lock_path)
                return {
                    "status": status,
                    "policy_source": policy_source,
                    "policy_hash": policy_hash,
                    "report_path": rel_json,
                    "report_md_path": rel_md,
                }
            autoselect_payload = _run_cmd_json_with_perf(
                op_name="work-intake-autoselect",
                func=cmd_work_intake_autoselect,
                args=argparse.Namespace(workspace_root=str(workspace_root), limit=str(auto_select_limit)),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ops_called.append("work-intake-autoselect")
            selection_path = autoselect_payload.get("selection_path") if isinstance(autoselect_payload, dict) else None
            if isinstance(selection_path, str) and selection_path:
                evidence_paths.append(selection_path)
        dispatch_summary: dict[str, Any] | None = None
        dispatch_plan_path = ""
        dispatched_extensions: list[str] = []
        dispatch_jobs_started = 0
        dispatch_jobs_polled = 0
        dispatch_idle_reason = ""
        ignored_count = 0
        ignored_by_reason: dict[str, int] = {}
        skipped_count = 0
        skipped_by_reason: dict[str, int] = {}
        exec_payload: dict[str, Any] | None = None
        exec_path = ""
        if auto_mode_enabled and allow_apply:
            intake_items: list[dict[str, Any]] = []
            intake_path = Path(work_intake_path) if isinstance(work_intake_path, str) else None
            if intake_path is not None:
                if not intake_path.is_absolute():
                    intake_path = workspace_root / intake_path
                if intake_path.exists():
                    try:
                        intake_obj = _load_json(intake_path)
                    except Exception:
                        intake_obj = {}
                    items = intake_obj.get("items") if isinstance(intake_obj, dict) else None
                    if isinstance(items, list):
                        intake_items = [i for i in items if isinstance(i, dict)]
            dispatch_plan = plan_auto_mode_dispatch(
                items=intake_items,
                policy=auto_mode_policy,
                workspace_root=workspace_root,
            )
            dispatched_extensions = list(dispatch_plan.get("dispatched_extensions") or [])
            selected_ids = list(dispatch_plan.get("selected_ids") or [])
            if selected_ids:
                selection_path = write_selection_file(
                    workspace_root=workspace_root,
                    selected_ids=selected_ids,
                    notes=["PROGRAM_LED=true", "AUTO_MODE=true"],
                )
                evidence_paths.append(selection_path)
                work_intake_payload = _run_cmd_json_with_perf(
                    op_name="work-intake-check",
                    func=cmd_work_intake_check,
                    args=argparse.Namespace(
                        workspace_root=str(workspace_root),
                        mode="strict",
                        chat="false",
                        detail="false",
                    ),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ops_called.append("work-intake-check")
                work_intake_path = work_intake_payload.get("work_intake_path") if isinstance(work_intake_payload, dict) else work_intake_path
                if isinstance(work_intake_path, str) and work_intake_path:
                    evidence_paths.append(work_intake_path)
            job_candidates = dispatch_plan.get("job_candidates") if isinstance(dispatch_plan.get("job_candidates"), list) else []
            for job in job_candidates[: max(0, int(max_dispatch_jobs))]:
                if not can_start_github:
                    dispatch_idle_reason = "OP_NOT_ALLOWED"
                    break
                extension_id = str(job.get("extension_id") or "")
                job_kind = str(job.get("job_kind") or "")
                allow_network, net_reason = auto_mode_network_allowed(
                    workspace_root=workspace_root, policy=auto_mode_policy, extension_id=extension_id
                )
                dry_run = "false" if allow_network else "true"
                start_payload = _run_cmd_json_with_perf(
                    op_name="github-ops-job-start",
                    func=cmd_github_ops_job_start,
                    args=argparse.Namespace(
                        workspace_root=str(workspace_root),
                        kind=job_kind,
                        dry_run=dry_run,
                    ),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ops_called.append("github-ops-job-start")
                dispatch_jobs_started += 1
                report_path = start_payload.get("job_report_path") if isinstance(start_payload, dict) else None
                if isinstance(report_path, str) and report_path:
                    evidence_paths.append(report_path)
                index_path = start_payload.get("jobs_index_path") if isinstance(start_payload, dict) else None
                if isinstance(index_path, str) and index_path:
                    evidence_paths.append(index_path)
                if not allow_network:
                    notes.append(f"auto_mode_network_gate={net_reason}")
            release_candidates = (
                dispatch_plan.get("release_candidates") if isinstance(dispatch_plan.get("release_candidates"), list) else []
            )
            if release_candidates and "release-check" in allowed_ops:
                release_payload = _run_cmd_json_with_perf(
                    op_name="release-check",
                    func=cmd_release_check,
                    args=argparse.Namespace(workspace_root=str(workspace_root), channel="", chat="false"),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ops_called.append("release-check")
                report_path = release_payload.get("report_path") if isinstance(release_payload, dict) else None
                if isinstance(report_path, str) and report_path:
                    evidence_paths.append(report_path)
            if "work-intake-exec-ticket" in allowed_ops:
                limit = max(1, int(max_dispatch_actions))
                exec_payload = _run_cmd_json_with_perf(
                    op_name="work-intake-exec-ticket",
                    func=cmd_work_intake_exec_ticket,
                    args=argparse.Namespace(workspace_root=str(workspace_root), limit=limit, chat="false"),
                    workspace_root=workspace_root,
                    perf_cfg=perf_cfg,
                )
                ops_called.append("work-intake-exec-ticket")
                exec_path = exec_payload.get("work_intake_exec_path") if isinstance(exec_payload, dict) else None
                if isinstance(exec_path, str) and exec_path:
                    evidence_paths.append(exec_path)
            plan_candidates = (
                dispatch_plan.get("plan_candidates") if isinstance(dispatch_plan.get("plan_candidates"), list) else []
            )
            dispatch_plan_path = write_plan_only(
                workspace_root=workspace_root,
                plan_candidates=plan_candidates,
                reason="AUTO_MODE_PLAN_ONLY",
            )
            if dispatch_plan_path:
                evidence_paths.append(dispatch_plan_path)
            applied = int(exec_payload.get("applied_count") or 0) if isinstance(exec_payload, dict) else 0
            planned = int(exec_payload.get("planned_count") or 0) if isinstance(exec_payload, dict) else 0
            idle = int(exec_payload.get("idle_count") or 0) if isinstance(exec_payload, dict) else 0
            ignored_count = int(exec_payload.get("ignored_count") or 0) if isinstance(exec_payload, dict) else 0
            raw_ignored = exec_payload.get("ignored_by_reason") if isinstance(exec_payload, dict) else None
            if isinstance(raw_ignored, dict):
                ignored_by_reason = {
                    str(k): int(raw_ignored.get(k) or 0)
                    for k in sorted(raw_ignored)
                    if isinstance(k, str)
                }
            skipped_count = int(exec_payload.get("skipped_count") or 0) if isinstance(exec_payload, dict) else 0
            raw_skipped = exec_payload.get("skipped_by_reason") if isinstance(exec_payload, dict) else None
            if isinstance(raw_skipped, dict):
                skipped_by_reason = {
                    str(k): int(raw_skipped.get(k) or 0)
                    for k in sorted(raw_skipped)
                    if isinstance(k, str)
                }
            selected_count = int(exec_payload.get("selected_count") or 0) if isinstance(exec_payload, dict) else len(selected_ids)
            decision_needed_count = (
                int(exec_payload.get("decision_needed_count") or 0) if isinstance(exec_payload, dict) else 0
            )
            decision_inbox_path = exec_payload.get("decision_inbox_path") if isinstance(exec_payload, dict) else None
            decision_inbox_built = False
            if decision_needed_count > 0 and not decision_inbox_path:
                try:
                    from src.ops.decision_inbox import run_decision_inbox_build
                except Exception:
                    run_decision_inbox_build = None
                if run_decision_inbox_build:
                    inbox_payload = run_decision_inbox_build(workspace_root=workspace_root)
                    decision_inbox_path = (
                        inbox_payload.get("decision_inbox_path") if isinstance(inbox_payload, dict) else None
                    )
                    decision_inbox_built = True
            if isinstance(decision_inbox_path, str) and decision_inbox_path:
                evidence_paths.append(decision_inbox_path)
                if decision_inbox_built:
                    ops_called.append("decision-inbox-build")
            if plan_candidates:
                planned += len([c for c in plan_candidates if isinstance(c, dict)])
            dispatch_summary = {
                "selected_count": int(selected_count),
                "dispatched_extensions": sorted({str(x) for x in dispatched_extensions if str(x)}),
                "jobs_started": int(dispatch_jobs_started),
                "jobs_polled": int(dispatch_jobs_polled),
                "applied_count": int(applied),
                "planned_count": int(planned),
                "idle_count": int(idle),
                "ignored_count": int(ignored_count),
                "ignored_by_reason": ignored_by_reason,
                "skipped_count": int(skipped_count),
                "skipped_by_reason": skipped_by_reason,
                "decision_needed_count": int(decision_needed_count),
            }
            if dispatch_plan_path:
                dispatch_summary["plan_path"] = dispatch_plan_path
            if isinstance(decision_inbox_path, str) and decision_inbox_path:
                dispatch_summary["decision_inbox_path"] = decision_inbox_path
            if not (dispatch_jobs_started or applied or planned or idle):
                status = "IDLE"
                error_code = "NO_AUTO_MODE_ACTIONS"
                dispatch_idle_reason = "NO_CANDIDATES"
        if (
            allow_apply
            and not auto_mode_enabled
            and can_start_github
            and _intake_suggests_extension(workspace_root, work_intake_path, "PRJ-GITHUB-OPS")
        ):
            start_payload = _run_cmd_json_with_perf(
                op_name="github-ops-job-start",
                func=cmd_github_ops_job_start,
                args=argparse.Namespace(workspace_root=str(workspace_root), kind="SMOKE_FULL", dry_run="false"),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ops_called.append("github-ops-job-start")
            report_path = start_payload.get("job_report_path") if isinstance(start_payload, dict) else None
            if isinstance(report_path, str) and report_path:
                evidence_paths.append(report_path)
            index_path = start_payload.get("jobs_index_path") if isinstance(start_payload, dict) else None
            if isinstance(index_path, str) and index_path:
                evidence_paths.append(index_path)
            ui_payload = _run_cmd_json_with_perf(
                op_name="ui-snapshot-bundle",
                func=cmd_ui_snapshot,
                args=argparse.Namespace(
                    workspace_root=str(workspace_root),
                    out=".cache/reports/ui_snapshot_bundle.v1.json",
                ),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ui_report = ui_payload.get("report_path") if isinstance(ui_payload, dict) else None
            if isinstance(ui_report, str) and ui_report:
                evidence_paths.append(ui_report)
            heartbeat_rel = _write_heartbeat(
                heartbeat_path,
                workspace_root=workspace_root,
                tick_id=tick_id,
                status="OK",
                error_code=None,
                window_bucket=window_bucket,
                policy_hash=policy_hash,
                notes=notes + ["PROGRAM_LED=true", "NETWORK=false", "START_ONLY=true", "GITHUB_START=true"],
            )
            evidence_paths.append(heartbeat_rel)
            report = {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": "OK",
                "error_code": None,
                "tick_id": tick_id,
                "workspace_root": str(workspace_root),
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "fast_gate": fast_gate,
                "jobs_started": int(job_stats.get("started", 0)) + 1,
                "jobs_polled": int(job_stats.get("polled", 0)),
                "jobs_running": int(job_stats.get("running", 0)),
                "jobs_failed": int(job_stats.get("failed", 0)),
                "jobs_passed": int(job_stats.get("passed", 0)),
                "queued_before": queued_before,
                "running_before": running_before,
                "queued_after": queued_after,
                "running_after": running_after,
                "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
                "ops_called": ["work-intake-check", "github-ops-job-start", "ui-snapshot-bundle"],
                "actions": {"applied": 0, "planned": 0, "idle": 0},
                "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                "notes": notes
                + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false", "START_ONLY=true", "GITHUB_START=true"],
            }
            report.update(preflight_meta)
            report.update(_active_meta("START_ONLY"))
            rel_json, rel_md = _write_tick_report(report, workspace_root)
            return {
                "status": "OK",
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "report_path": rel_json,
                "report_md_path": rel_md,
                "jobs_started": int(job_stats.get("started", 0)) + 1,
                "jobs_polled": int(job_stats.get("polled", 0)),
                "jobs_running": int(job_stats.get("running", 0)),
                "jobs_failed": int(job_stats.get("failed", 0)),
                "jobs_passed": int(job_stats.get("passed", 0)),
                "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
            }
        if exec_payload is None and allow_apply:
            limit = max(1, int(max_actions))
            exec_payload = _run_cmd_json_with_perf(
                op_name="work-intake-exec-ticket",
                func=cmd_work_intake_exec_ticket,
                args=argparse.Namespace(workspace_root=str(workspace_root), limit=limit, chat="false"),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ops_called.append("work-intake-exec-ticket")
            exec_path = exec_payload.get("work_intake_exec_path") if isinstance(exec_payload, dict) else None
            if isinstance(exec_path, str) and exec_path:
                evidence_paths.append(exec_path)
        elif exec_payload is None and not allow_apply:
            exec_payload = {
                "status": "IDLE",
                "error_code": preflight_reason,
                "applied_count": 0,
                "planned_count": 0,
                "idle_count": 0,
                "selected_count": 0,
                "ignored_count": 0,
                "ignored_by_reason": {},
                "skipped_count": 0,
                "decision_needed_count": 0,
            }
        sys_payload = _run_cmd_json_with_perf(
            op_name="system-status",
            func=cmd_system_status,
            args=argparse.Namespace(workspace_root=str(workspace_root), dry_run="false"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("system-status")
        sys_out = sys_payload.get("out_json") if isinstance(sys_payload, dict) else None
        if isinstance(sys_out, str):
            rel = _rel_to_workspace(Path(sys_out), workspace_root)
            if rel:
                evidence_paths.append(rel)
        portfolio_payload = _run_cmd_json_with_perf(
            op_name="portfolio-status",
            func=cmd_portfolio_status,
            args=argparse.Namespace(workspace_root=str(workspace_root), mode="json"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("portfolio-status")
        portfolio_path = portfolio_payload.get("report_path") if isinstance(portfolio_payload, dict) else None
        if isinstance(portfolio_path, str) and portfolio_path:
            evidence_paths.append(portfolio_path)
        ui_payload = _run_cmd_json_with_perf(
            op_name="ui-snapshot-bundle",
            func=cmd_ui_snapshot,
            args=argparse.Namespace(
                workspace_root=str(workspace_root),
                out=".cache/reports/ui_snapshot_bundle.v1.json",
            ),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("ui-snapshot-bundle")
        ui_report = ui_payload.get("report_path") if isinstance(ui_payload, dict) else None
        if isinstance(ui_report, str) and ui_report:
            evidence_paths.append(ui_report)
        applied = int(exec_payload.get("applied_count") or 0) if isinstance(exec_payload, dict) else 0
        planned = int(exec_payload.get("planned_count") or 0) if isinstance(exec_payload, dict) else 0
        idle = int(exec_payload.get("idle_count") or 0) if isinstance(exec_payload, dict) else 0
        ignored_count = int(exec_payload.get("ignored_count") or 0) if isinstance(exec_payload, dict) else 0
        raw_ignored = exec_payload.get("ignored_by_reason") if isinstance(exec_payload, dict) else None
        if isinstance(raw_ignored, dict):
            ignored_by_reason = {str(k): int(raw_ignored.get(k) or 0) for k in sorted(raw_ignored) if isinstance(k, str)}
        skipped_count = int(exec_payload.get("skipped_count") or 0) if isinstance(exec_payload, dict) else 0
        raw_skipped = exec_payload.get("skipped_by_reason") if isinstance(exec_payload, dict) else None
        if isinstance(raw_skipped, dict):
            skipped_by_reason = {str(k): int(raw_skipped.get(k) or 0) for k in sorted(raw_skipped) if isinstance(k, str)}
        selected_count = int(exec_payload.get("selected_count") or 0) if isinstance(exec_payload, dict) else 0
        decision_needed_count = int(exec_payload.get("decision_needed_count") or 0) if isinstance(exec_payload, dict) else 0
        decision_inbox_path = exec_payload.get("decision_inbox_path") if isinstance(exec_payload, dict) else None
        if isinstance(decision_inbox_path, str) and decision_inbox_path:
            evidence_paths.append(decision_inbox_path)
        idle_reason = str(exec_payload.get("error_code") or "") if isinstance(exec_payload, dict) else ""
        if dispatch_summary:
            applied = int(dispatch_summary.get("applied_count") or applied)
            planned = int(dispatch_summary.get("planned_count") or planned)
            idle = int(dispatch_summary.get("idle_count") or idle)
            ignored_count = int(dispatch_summary.get("ignored_count") or ignored_count)
            ignored_by_reason = dispatch_summary.get("ignored_by_reason") or ignored_by_reason
            skipped_count = int(dispatch_summary.get("skipped_count") or skipped_count)
            skipped_by_reason = dispatch_summary.get("skipped_by_reason") or skipped_by_reason
            selected_count = int(dispatch_summary.get("selected_count") or selected_count)
            decision_needed_count = int(dispatch_summary.get("decision_needed_count") or decision_needed_count)
            if not decision_inbox_path:
                decision_inbox_path = dispatch_summary.get("decision_inbox_path")
            if dispatch_idle_reason and not idle_reason:
                idle_reason = dispatch_idle_reason
        for payload in [work_intake_payload, exec_payload, sys_payload, portfolio_payload]:
            if not isinstance(payload, dict):
                status = "FAIL"
                error_code = "OP_OUTPUT_INVALID"
                break
            op_status = payload.get("status")
            if isinstance(op_status, str) and op_status not in {"OK", "WARN", "IDLE"}:
                status = "FAIL"
                error_code = "OP_FAILED"
                break
            if payload.get("return_code") not in {None, 0}:
                status = "FAIL"
                error_code = "OP_FAILED"
                break
        if planned > max_plans and status == "OK":
            status = "WARN"
            error_code = "PLANS_LIMIT_EXCEEDED"
        build_time_sinks_report(workspace_root, policy=jobs_policy)
        time_sinks_path = str(Path(".cache") / "reports" / "time_sinks.v1.json")
        evidence_paths.append(time_sinks_path)
        heartbeat_rel = _write_heartbeat(
            heartbeat_path,
            workspace_root=workspace_root,
            tick_id=tick_id,
            status=status,
            error_code=error_code,
            window_bucket=window_bucket,
            policy_hash=policy_hash,
            notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
        )
        evidence_paths.append(heartbeat_rel)
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": status,
            "error_code": error_code,
            "tick_id": tick_id,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "fast_gate": fast_gate,
            "jobs_started": int(job_stats.get("started", 0)),
            "jobs_polled": int(job_stats.get("polled", 0)),
            "jobs_running": int(job_stats.get("running", 0)),
            "jobs_failed": int(job_stats.get("failed", 0)),
            "jobs_passed": int(job_stats.get("passed", 0)),
            "jobs_archived_delta": int(job_stats.get("archived", 0)),
            "jobs_skipped_delta": int(job_stats.get("skipped", 0)),
            "poll_first_enforced": False,
            "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
            "queued_before": queued_before,
            "running_before": running_before,
            "queued_after": queued_after,
            "running_after": running_after,
            "ops_called": ops_called,
            "actions": {"applied": applied, "planned": planned, "idle": idle, "selected": selected_count},
            "ignored_count": int(ignored_count),
            "ignored_by_reason": ignored_by_reason,
            "skipped_count": int(skipped_count),
            "skipped_by_reason": skipped_by_reason,
            "decision_needed_count": int(decision_needed_count),
            "decision_inbox_path": decision_inbox_path or None,
            "idle_reason": idle_reason or None,
            "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        if dispatch_summary:
            report["dispatch_summary"] = dispatch_summary
        report.update(preflight_meta)
        report.update(_active_meta("NORMAL_FLOW"))
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": status,
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "work_intake_path": work_intake_path,
            "work_intake_exec_path": exec_path,
            "decision_inbox_path": decision_inbox_path,
            "system_status_path": sys_out,
            "portfolio_status_path": portfolio_path,
            "report_path": rel_json,
            "report_md_path": rel_md,
            "applied": applied,
            "planned": planned,
            "idle": idle,
            "jobs_started": int(job_stats.get("started", 0)),
            "jobs_polled": int(job_stats.get("polled", 0)),
            "jobs_running": int(job_stats.get("running", 0)),
            "jobs_failed": int(job_stats.get("failed", 0)),
            "jobs_passed": int(job_stats.get("passed", 0)),
            "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
        }
    finally:
        if tick_started_at is not None:
            elapsed_seconds = int(max(0, time.monotonic() - tick_started_at))
            updated_seconds = elapsed_seconds
            if isinstance(runtime_state.get("date"), str) and runtime_state.get("date") == runtime_day:
                updated_seconds += int(runtime_state.get("runtime_seconds", 0) or 0)
            _write_runtime_state(
                workspace_root,
                runtime_day=runtime_day,
                runtime_seconds=updated_seconds,
                now=datetime.now(timezone.utc),
                notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
            )
        _release_lock(lock_path)
