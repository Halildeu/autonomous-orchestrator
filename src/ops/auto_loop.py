from __future__ import annotations

import hashlib
import json
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.trace_meta import build_run_id, build_trace_meta, date_bucket_from_iso

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _normalize_ids(values: list[Any]) -> list[str]:
    return sorted({str(x) for x in values if isinstance(x, str) and x.strip()})


def _load_script_budget_report(core_root: Path, workspace_root: Path) -> tuple[Path | None, dict[str, Any]]:
    ws_path = workspace_root / ".cache" / "script_budget" / "report.json"
    core_path = core_root / ".cache" / "script_budget" / "report.json"
    report_path = ws_path if ws_path.exists() else core_path
    if not report_path.exists():
        return (None, {})
    try:
        obj = _load_json(report_path)
    except Exception:
        return (report_path, {})
    return (report_path, obj if isinstance(obj, dict) else {})


def _load_selection_ids(workspace_root: Path, selection_rel: str | None) -> list[str]:
    path = workspace_root / (selection_rel or ".cache/index/work_intake_selection.v1.json")
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    selected = obj.get("selected_ids")
    if not isinstance(selected, list):
        selected = obj.get("intake_ids")
    if not isinstance(selected, list):
        return []
    return _normalize_ids([x for x in selected if isinstance(x, str)])


def _collect_exec_details(exec_obj: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    entries = exec_obj.get("entries") if isinstance(exec_obj.get("entries"), list) else []
    applied_ids: list[str] = []
    planned_ids: list[str] = []
    skipped_ids: list[str] = []
    selected_ids: list[str] = []
    applied_evidence: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        intake_id = str(entry.get("intake_id") or "").strip()
        status = str(entry.get("status") or "").strip().upper()
        if entry.get("autopilot_selected") is True and intake_id:
            selected_ids.append(intake_id)
        if not intake_id:
            continue
        if status == "APPLIED":
            applied_ids.append(intake_id)
            evidence_paths = entry.get("evidence_paths") if isinstance(entry.get("evidence_paths"), list) else []
            applied_evidence.extend([p for p in evidence_paths if isinstance(p, str) and p.strip()])
            note_path = str(entry.get("note_path") or "").strip()
            if note_path:
                applied_evidence.append(note_path)
        elif status == "PLANNED":
            planned_ids.append(intake_id)
        elif status == "SKIPPED":
            skipped_ids.append(intake_id)
    return (
        _normalize_ids(applied_ids),
        _normalize_ids(planned_ids),
        _normalize_ids(skipped_ids),
        _normalize_ids(selected_ids),
        sorted({p for p in applied_evidence if p}),
    )


def _write_auto_loop_apply_details(
    *, workspace_root: Path, auto_loop_report: dict[str, Any], auto_loop_rel: str
) -> dict[str, Any]:
    exec_rel = str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json")
    exec_path = workspace_root / exec_rel
    exec_obj: dict[str, Any] = {}
    if exec_path.exists():
        try:
            loaded = _load_json(exec_path)
            if isinstance(loaded, dict):
                exec_obj = loaded
        except Exception:
            exec_obj = {}

    applied_ids, planned_ids, skipped_ids, selected_ids, applied_evidence = _collect_exec_details(exec_obj)
    selection_rel = auto_loop_report.get("selection_path") if isinstance(auto_loop_report.get("selection_path"), str) else None
    selected_ids = _load_selection_ids(workspace_root, selection_rel) or selected_ids
    limit_reached_ids = sorted({x for x in selected_ids if x not in set(applied_ids + planned_ids + skipped_ids)})

    canonical_counts = {
        "applied": len(applied_ids),
        "planned": len(planned_ids),
        "skipped": len(skipped_ids),
        "limit_reached": len(limit_reached_ids),
        "applied_intake_ids": applied_ids,
        "planned_intake_ids": planned_ids,
        "limit_reached_intake_ids": limit_reached_ids,
    }

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "counts": canonical_counts,
        "applied_intake_ids": applied_ids,
        "planned_intake_ids": planned_ids,
        "limit_reached_intake_ids": limit_reached_ids,
        "applied_evidence_paths": applied_evidence,
        "skipped_limit_intake_ids": limit_reached_ids,
        "next_shortlist_intake_ids": limit_reached_ids,
        "source_paths": {
            "auto_loop_report": auto_loop_rel,
            "work_intake_exec_report": exec_rel if exec_path.exists() else "",
            "selection_path": selection_rel or str(Path(".cache") / "index" / "work_intake_selection.v1.json"),
            "work_intake": auto_loop_report.get("work_intake_path"),
        },
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true", "network_used=false"],
    }

    out_json = workspace_root / ".cache" / "reports" / "auto_loop_apply_details.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "auto_loop_apply_details.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "# Auto Loop Apply Details",
        f"- generated_at: {report['generated_at']}",
        f"- applied: {canonical_counts['applied']}",
        f"- planned: {canonical_counts['planned']}",
        f"- skipped: {canonical_counts['skipped']}",
        f"- limit_reached: {canonical_counts['limit_reached']}",
    ]
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    report["report_path"] = _rel_path(workspace_root, out_json)
    report["report_md_path"] = _rel_path(workspace_root, out_md)
    return report


def _load_auto_loop_override(workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_auto_loop.override.v1.json"
    if not override_path.exists():
        return ({}, notes)
    try:
        obj = _load_json(override_path)
    except Exception:
        notes.append("auto_loop_override_invalid")
        return ({}, notes)
    if not isinstance(obj, dict):
        notes.append("auto_loop_override_invalid")
        return ({}, notes)
    notes.append("auto_loop_override_loaded")
    return (obj, notes)


def _maybe_run_memory_health(*, workspace_root: Path, notes: list[str]) -> str | None:
    try:
        from src.ops.memory_health import run_memory_healthcheck

        res = run_memory_healthcheck(workspace_root=workspace_root)
        path = res.get("report_path") if isinstance(res, dict) else None
        if isinstance(path, str) and path:
            notes.append("memory_healthcheck=ok")
            return path
        notes.append("memory_healthcheck=missing_path")
        return None
    except Exception:
        notes.append("memory_healthcheck=fail")
        return None


def _maybe_run_memory_smoke(
    *, workspace_root: Path, notes: list[str], auto_loop_override: dict[str, Any]
) -> tuple[str | None, str]:
    enabled = auto_loop_override.get("memory_smoke_enabled")
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    if enabled is not True:
        notes.append("memory_smoke=disabled")
        return (None, "SKIP")

    period = auto_loop_override.get("memory_smoke_period_seconds")
    try:
        period_seconds = int(period) if period is not None else 0
    except Exception:
        period_seconds = 0

    report_path = workspace_root / ".cache" / "reports" / "memory_smoke.v1.json"
    if period_seconds > 0 and report_path.exists():
        age = time.time() - report_path.stat().st_mtime
        if age < period_seconds:
            notes.append("memory_smoke=skip_recent")
            return (_rel_path(workspace_root, report_path), "SKIP")

    try:
        from src.ops.memory_health import run_memory_smoke

        res = run_memory_smoke(workspace_root=workspace_root)
        path = res.get("report_path") if isinstance(res, dict) else None
        status = str(res.get("status") or "UNKNOWN") if isinstance(res, dict) else "UNKNOWN"
        if isinstance(path, str) and path:
            notes.append("memory_smoke=ran")
            return (path, status)
        notes.append("memory_smoke=ran_missing_path")
        return (None, status)
    except Exception:
        notes.append("memory_smoke=fail")
        return (None, "FAIL")


def _update_autopilot_apply_override(*, workspace_root: Path, max_apply_per_tick: int) -> None:
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_autopilot_apply.override.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                payload = obj
        except Exception:
            payload = {}
    defaults = payload.get("defaults") if isinstance(payload.get("defaults"), dict) else {}
    defaults["max_apply_per_tick"] = int(max_apply_per_tick)
    payload["defaults"] = defaults
    if not isinstance(payload.get("version"), str):
        payload["version"] = "v1"
    override_path.write_text(_dump_json(payload), encoding="utf-8")


def _update_auto_mode_override(*, workspace_root: Path, max_actions_per_tick: int) -> None:
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_auto_mode.override.v1.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                payload = obj
        except Exception:
            payload = {}
    limits = payload.get("limits") if isinstance(payload.get("limits"), dict) else {}
    limits["max_actions_per_tick"] = int(max_actions_per_tick)
    payload["limits"] = limits
    if not isinstance(payload.get("version"), str):
        payload["version"] = "v1"
    override_path.write_text(_dump_json(payload), encoding="utf-8")


def _pick_soft_offender(report: dict[str, Any]) -> dict[str, Any] | None:
    offenders = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    items = [
        item
        for item in offenders
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and str(item.get("path") or "").strip()
    ]
    if not items:
        return None
    items.sort(key=lambda x: str(x.get("path") or ""))
    return items[0]


def _write_self_heal_scaffold(*, workspace_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    soft_offender = _pick_soft_offender(report)
    if not soft_offender:
        return {}
    offender_path = str(soft_offender.get("path") or "").strip()
    if not offender_path:
        return {}

    overrides_dir = workspace_root / ".cache" / "policy_overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    override_path = overrides_dir / "policy_core_immutability.override.v1.json"
    override_payload = {
        "version": "v1",
        "ssot_write_allowlist": [offender_path],
        "notes": ["AUTO_LOOP_SOFT_NARROWING=true"],
    }
    override_path.write_text(_dump_json(override_payload), encoding="utf-8")

    plan_dir = workspace_root / ".cache" / "reports" / "chg"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_id = "CHG-M0-SOFT-AUTO-" + hashlib.sha256(offender_path.encode("utf-8")).hexdigest()[:12]
    plan_path = plan_dir / f"{plan_id}.plan.json"
    plan_payload = {
        "version": "v1",
        "change_id": plan_id,
        "workspace_root": str(workspace_root),
        "target_path": offender_path,
        "intent": "workspace_override_only",
        "status": "PLANNED_NO_APPLY",
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    plan_path.write_text(_dump_json(plan_payload), encoding="utf-8")

    closeout_path = plan_dir / f"{plan_id}.closeout.json"
    closeout_payload = {
        "version": "v1",
        "change_id": plan_id,
        "workspace_root": str(workspace_root),
        "status": "NO_APPLY",
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    closeout_path.write_text(_dump_json(closeout_payload), encoding="utf-8")

    return {
        "soft_offender_path": offender_path,
        "override_path": _rel_path(workspace_root, override_path),
        "plan_path": _rel_path(workspace_root, plan_path),
        "closeout_path": _rel_path(workspace_root, closeout_path),
    }


def _int_from_any(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _compute_pr_merge_promotion_plan(*, github_ops_report: dict[str, Any]) -> dict[str, Any]:
    git_state = github_ops_report.get("git_state") if isinstance(github_ops_report.get("git_state"), dict) else {}
    live_gate = github_ops_report.get("live_gate") if isinstance(github_ops_report.get("live_gate"), dict) else {}

    dirty_tree = bool(git_state.get("dirty_tree", False))
    ahead = _int_from_any(git_state.get("ahead"))
    behind = _int_from_any(git_state.get("behind"))
    index_lock = bool(git_state.get("index_lock", False))

    needed = bool(dirty_tree or ahead > 0)
    gate_enabled = bool(live_gate.get("enabled", False))

    # Fail-closed: do not attempt promotion if repo is behind remote or git index.lock is present.
    if not needed:
        return {
            "needed": False,
            "should_run": False,
            "skip_reason": "NOT_NEEDED",
            "git_state": {"dirty_tree": dirty_tree, "ahead": ahead, "behind": behind, "index_lock": index_lock},
            "gate": {"enabled": gate_enabled},
        }
    if behind > 0:
        return {
            "needed": True,
            "should_run": False,
            "skip_reason": "BEHIND_REMOTE",
            "git_state": {"dirty_tree": dirty_tree, "ahead": ahead, "behind": behind, "index_lock": index_lock},
            "gate": {"enabled": gate_enabled},
        }
    if index_lock:
        return {
            "needed": True,
            "should_run": False,
            "skip_reason": "GIT_INDEX_LOCK_PRESENT",
            "git_state": {"dirty_tree": dirty_tree, "ahead": ahead, "behind": behind, "index_lock": index_lock},
            "gate": {"enabled": gate_enabled},
        }
    if not gate_enabled:
        return {
            "needed": True,
            "should_run": False,
            "skip_reason": "GITHUB_OPS_GATE_BLOCKED",
            "git_state": {"dirty_tree": dirty_tree, "ahead": ahead, "behind": behind, "index_lock": index_lock},
            "gate": {
                "enabled": gate_enabled,
                "network_enabled": bool(live_gate.get("network_enabled", False)),
                "env_flag_set": bool(live_gate.get("env_flag_set", False)),
                "env_key_present": bool(live_gate.get("env_key_present", False)),
            },
        }
    return {
        "needed": True,
        "should_run": True,
        "skip_reason": None,
        "git_state": {"dirty_tree": dirty_tree, "ahead": ahead, "behind": behind, "index_lock": index_lock},
        "gate": {"enabled": gate_enabled},
    }


def _work_intake_check_payload(*, workspace_root: Path, mode: str) -> dict[str, Any]:
    import argparse
    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status
    from src.ops.roadmap_cli import cmd_portfolio_status

    build_res = run_work_intake_build(workspace_root=workspace_root)
    work_intake_path = build_res.get("work_intake_path") if isinstance(build_res, dict) else None

    intake_obj: dict[str, Any] = {}
    if isinstance(work_intake_path, str) and work_intake_path:
        intake_path_abs = (workspace_root / work_intake_path).resolve()
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

    sys_result = run_system_status(workspace_root=workspace_root, core_root=_repo_root(), dry_run=False, max_age_seconds=30)
    sys_out = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    sys_rel = None
    if isinstance(sys_out, str):
        sys_rel = Path(sys_out).resolve()
        try:
            sys_rel = sys_rel.relative_to(workspace_root)
        except Exception:
            sys_rel = None

    portfolio_buf = StringIO()
    with redirect_stdout(portfolio_buf), redirect_stderr(portfolio_buf):
        cmd_portfolio_status(argparse.Namespace(workspace_root=str(workspace_root), mode="json"))
    portfolio_report = workspace_root / ".cache" / "reports" / "portfolio_status.v1.json"
    portfolio_rel = ".cache/reports/portfolio_status.v1.json" if portfolio_report.exists() else ""

    status = build_res.get("status") if isinstance(build_res, dict) else "WARN"
    error_code = None
    plan_dir = workspace_root / ".cache" / "reports" / "chg"
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

    return {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(workspace_root),
        "work_intake_path": work_intake_path,
        "items_count": len(items),
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions[:5],
        "next_intake_focus": next_intake_focus,
        "system_status_path": str(sys_rel) if isinstance(sys_rel, Path) else None,
        "portfolio_status_path": portfolio_rel,
        "notes": [f"mode={mode}", "PROGRAM_LED=true"],
    }


def run_auto_loop(*, workspace_root: Path, budget_seconds: int, chat: bool = False) -> dict[str, Any]:
    from src.ops.decision_inbox import run_decision_apply_bulk, run_decision_inbox_build, run_decision_inbox_show
    from src.ops.doer_loop_lock import (
        acquire_doer_loop_lock,
        load_loop_lock_ttl_seconds,
        owner_session_from_env,
        owner_tag_from_env,
        release_doer_loop_lock,
        touch_doer_loop_lock,
    )
    from src.ops.work_intake_autoselect import run_work_intake_autoselect
    from src.prj_airunner.airunner_run import run_airunner_baseline, run_airunner_run
    from src.ops.system_status_report import run_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    core_root = _repo_root()
    lock_run_id = build_run_id(
        workspace_root=workspace_root,
        op_name="auto-loop-lock",
        inputs={"budget_seconds": int(budget_seconds or 0)},
        date_bucket=date_bucket_from_iso(_now_iso()),
    )
    lock_owner_tag = owner_tag_from_env()
    lock_owner_session = owner_session_from_env()
    lock_ttl = load_loop_lock_ttl_seconds(core_root=core_root, workspace_root=workspace_root)
    lock_res = acquire_doer_loop_lock(
        workspace_root=workspace_root,
        owner_tag=lock_owner_tag,
        owner_session=lock_owner_session,
        run_id=lock_run_id,
        ttl_seconds=lock_ttl,
    )
    if lock_res.get("status") == "LOCKED":
        out_json = workspace_root / ".cache" / "reports" / "auto_loop.v1.json"
        out_md = workspace_root / ".cache" / "reports" / "auto_loop.v1.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "IDLE",
            "error_code": "LOCKED_LOOP",
            "counts": {
                "decision_pending_before": 0,
                "decision_pending_after": 0,
                "bulk_applied_count": 0,
                "selected_count": 0,
                "doer_counts": {"applied": 0, "planned": 0, "skipped": 0, "skipped_by_reason": {}},
            },
            "lock_path": lock_res.get("lock_path"),
            "lock_owner_tag": lock_res.get("owner_tag"),
            "lock_owner_session": lock_res.get("owner_session"),
            "lock_expires_at": lock_res.get("expires_at"),
            "lock_run_id": lock_res.get("run_id"),
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
        }
        out_json.write_text(_dump_json(report), encoding="utf-8")
        out_md.write_text("# Auto Loop\n- status: IDLE\n- error_code: LOCKED_LOOP\n", encoding="utf-8")
        return {"status": "IDLE", "report_path": _rel_path(workspace_root, out_json)}
    notes = ["PROGRAM_LED=true", "NO_NETWORK=true"]
    auto_loop_override, override_notes = _load_auto_loop_override(workspace_root)
    notes.extend(override_notes)
    override_budget = auto_loop_override.get("budget_seconds") if isinstance(auto_loop_override, dict) else None
    if isinstance(override_budget, int) and override_budget > 0:
        budget_seconds = int(override_budget)
        notes.append("auto_loop_budget_override=true")
    max_apply_per_run = auto_loop_override.get("max_apply_per_run") if isinstance(auto_loop_override, dict) else None
    autoselect_limit = 20
    if isinstance(max_apply_per_run, int) and max_apply_per_run > 0:
        autoselect_limit = int(max_apply_per_run)
        notes.append("auto_loop_max_apply_per_run_override=true")
    max_apply_per_tick = auto_loop_override.get("max_apply_per_tick") if isinstance(auto_loop_override, dict) else None
    if isinstance(max_apply_per_tick, int) and max_apply_per_tick > 0:
        _update_autopilot_apply_override(workspace_root=workspace_root, max_apply_per_tick=max_apply_per_tick)
        _update_auto_mode_override(workspace_root=workspace_root, max_actions_per_tick=max_apply_per_tick)
        notes.append("auto_loop_max_apply_per_tick_override=true")

    memory_health_path = _maybe_run_memory_health(workspace_root=workspace_root, notes=notes)
    memory_smoke_path, memory_smoke_status = _maybe_run_memory_smoke(
        workspace_root=workspace_root,
        notes=notes,
        auto_loop_override=auto_loop_override if isinstance(auto_loop_override, dict) else {},
    )

    run_decision_inbox_build(workspace_root=workspace_root)
    decision_show = run_decision_inbox_show(workspace_root=workspace_root)
    pending_before = int(decision_show.get("decisions_count") or 0)

    bulk_res = run_decision_apply_bulk(workspace_root=workspace_root, mode="safe_defaults", decision_ids=None)
    pending_after = int(bulk_res.get("pending_decisions_after") or 0)
    bulk_applied = int(bulk_res.get("applied_count") or 0)

    intake_payload = _work_intake_check_payload(workspace_root=workspace_root, mode="strict")
    autoselect = run_work_intake_autoselect(workspace_root=workspace_root, limit=autoselect_limit, mode="safe_first")
    selected_count = int(autoselect.get("selected_count") or 0)

    baseline_res = run_airunner_baseline(workspace_root=workspace_root)
    run_res = run_airunner_run(
        workspace_root=workspace_root,
        ticks=2,
        mode="no_wait",
        budget_seconds=int(budget_seconds) if int(budget_seconds) > 0 else None,
    )
    if lock_res.get("lease_id"):
        touch_doer_loop_lock(workspace_root=workspace_root, lease_id=str(lock_res.get("lease_id") or ""))

    # --- Optional autopromotion lane (A1): if repo is dirty/ahead, open PR -> merge (no release) ---
    github_ops_report_rel = str(Path(".cache") / "reports" / "github_ops_report.v1.json")
    github_ops_report: dict[str, Any] = {}
    try:
        from src.prj_github_ops.github_ops import build_github_ops_report

        loaded = build_github_ops_report(workspace_root=workspace_root)
        if isinstance(loaded, dict):
            github_ops_report = loaded
    except Exception:
        github_ops_report = {}
        notes.append("auto_loop_promotion_github_ops_report_unavailable")

    promotion_plan = _compute_pr_merge_promotion_plan(github_ops_report=github_ops_report)
    pr_merge_res: dict[str, Any] | None = None
    pr_merge_report_path: str | None = None
    promotion_status = "SKIP"
    promotion_error_code: str | None = None
    promotion_notes: list[str] = []

    if bool(promotion_plan.get("needed")):
        skip_reason = promotion_plan.get("skip_reason")
        if isinstance(skip_reason, str) and skip_reason and skip_reason != "NOT_NEEDED":
            promotion_notes.append(f"skip_reason:{skip_reason}")

    if promotion_plan.get("should_run") is True:
        try:
            from src.prj_release_automation.pr_merge_e2e import run_pr_merge_e2e

            pr_merge_res = run_pr_merge_e2e(
                workspace_root=workspace_root,
                base_branch="main",
                allow_network=True,
                dry_run=False,
            )
        except Exception:
            pr_merge_res = {"status": "FAIL", "error_code": "PR_MERGE_E2E_EXCEPTION"}

        promotion_status = str((pr_merge_res or {}).get("status") or "FAIL")
        promotion_error_code = str((pr_merge_res or {}).get("error_code") or "") or None
        pr_merge_report_path = pr_merge_res.get("report_path") if isinstance(pr_merge_res, dict) else None
        if isinstance(pr_merge_report_path, str) and pr_merge_report_path:
            promotion_notes.append("pr_merge_report_written")
        if promotion_status == "OK":
            promotion_notes.append("pr_merge_e2e_ok")
        else:
            promotion_notes.append("pr_merge_e2e_not_ok")
        # This step uses git push + GitHub API (network) when it runs.
        notes[:] = [n for n in notes if n != "NO_NETWORK=true"]
        notes.append("NO_NETWORK=false")
        notes.append("NETWORK_USED=true")

    doer_counts = run_res.get("doer_processed_count") if isinstance(run_res.get("doer_processed_count"), dict) else {}
    raw_skipped = doer_counts.get("skipped_by_reason") if isinstance(doer_counts.get("skipped_by_reason"), dict) else {}
    doer_counts = {
        "applied": int(doer_counts.get("applied") or 0),
        "planned": int(doer_counts.get("planned") or 0),
        "skipped": int(doer_counts.get("skipped") or 0),
        "skipped_by_reason": {
            k: int(raw_skipped.get(k))
            for k in sorted(raw_skipped)
            if isinstance(raw_skipped.get(k), int)
        },
    }
    doer_actions_total = int(doer_counts.get("applied") or 0) + int(doer_counts.get("planned") or 0) + int(
        doer_counts.get("skipped") or 0
    )

    report_path, sb_report = _load_script_budget_report(core_root, workspace_root)
    self_heal = {}
    soft_exceeded = len(sb_report.get("exceeded_soft") or []) if isinstance(sb_report.get("exceeded_soft"), list) else 0
    if soft_exceeded > 0:
        self_heal = _write_self_heal_scaffold(workspace_root=workspace_root, report=sb_report)

    counts = {
        "decision_pending_before": pending_before,
        "decision_pending_after": pending_after,
        "bulk_applied_count": bulk_applied,
        "selected_count": selected_count,
        "doer_counts": doer_counts,
        "doer_actions_total": doer_actions_total,
    }

    status = "OK"
    if (
        pending_before == 0
        and bulk_applied == 0
        and selected_count == 0
        and doer_counts.get("applied", 0) == 0
        and doer_counts.get("planned", 0) == 0
        and doer_counts.get("skipped", 0) == 0
    ):
        status = "IDLE"

    if intake_payload.get("status") not in {"OK", "WARN", "IDLE"}:
        status = "WARN"
    if bulk_res.get("status") not in {"OK", "WARN", "IDLE"}:
        status = "WARN"
    if run_res.get("status") not in {"OK", "WARN", "IDLE"}:
        status = "WARN"

    if promotion_plan.get("should_run") is True and promotion_status != "OK":
        status = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "counts": counts,
        "decision_inbox_path": decision_show.get("decision_inbox_path"),
        "decision_inbox_md_path": decision_show.get("decision_inbox_md_path"),
        "decision_pending_before": pending_before,
        "decision_pending_after": pending_after,
        "bulk_apply_report_path": bulk_res.get("report_path"),
        "bulk_applied_count": bulk_applied,
        "bulk_skipped_count": int(bulk_res.get("skipped_count") or 0),
        "work_intake_path": intake_payload.get("work_intake_path"),
        "selection_path": autoselect.get("selection_path"),
        "selected_count": selected_count,
        "airunner_baseline_path": baseline_res.get("report_path"),
        "airunner_run_path": run_res.get("run_path"),
        "airunner_deltas_path": run_res.get("deltas_path"),
        "memory_health_path": memory_health_path,
        "memory_smoke_path": memory_smoke_path,
        "memory_smoke_status": memory_smoke_status,
        "github_ops_report_path": github_ops_report_rel if (workspace_root / github_ops_report_rel).exists() else None,
        "pr_merge_e2e_report_path": pr_merge_report_path,
        "pr_merge_e2e": {
            "plan": promotion_plan,
            "status": promotion_status,
            "error_code": promotion_error_code,
            "report_path": pr_merge_report_path,
            "notes": sorted({str(x) for x in promotion_notes if isinstance(x, str) and x.strip()}),
        },
        "system_status_path": None,
        "ui_snapshot_path": None,
        "script_budget_report_path": _rel_path(workspace_root, report_path) if report_path else None,
        "self_heal": self_heal,
        "notes": notes,
    }

    run_id = build_run_id(
        workspace_root=workspace_root,
        op_name="auto-loop",
        inputs={
            "budget_seconds": int(budget_seconds),
            "decision_pending_before": pending_before,
            "selected_count": selected_count,
        },
        date_bucket=date_bucket_from_iso(report["generated_at"]),
    )

    out_json = workspace_root / ".cache" / "reports" / "auto_loop.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "auto_loop.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "# Auto Loop",
        f"- generated_at: {report['generated_at']}",
        f"- status: {report['status']}",
        f"- decision_pending_before: {pending_before}",
        f"- decision_pending_after: {pending_after}",
        f"- bulk_applied_count: {bulk_applied}",
        f"- selected_count: {selected_count}",
        f"- doer_applied: {doer_counts.get('applied', 0)}",
        f"- doer_planned: {doer_counts.get('planned', 0)}",
        f"- doer_skipped: {doer_counts.get('skipped', 0)}",
    ]
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    apply_details = _write_auto_loop_apply_details(
        workspace_root=workspace_root,
        auto_loop_report=report,
        auto_loop_rel=_rel_path(workspace_root, out_json),
    )
    sys_res = run_system_status(workspace_root=workspace_root, core_root=core_root, dry_run=False)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=workspace_root)

    report["apply_details_path"] = apply_details.get("report_path")
    report["apply_details_md_path"] = apply_details.get("report_md_path")
    report["system_status_path"] = sys_res.get("out_json")
    report["ui_snapshot_path"] = ui_snapshot.get("report_path")

    evidence_paths = report.get("evidence_paths") if isinstance(report.get("evidence_paths"), list) else []
    report_rel = _rel_path(workspace_root, out_json)
    if report_rel and report_rel not in evidence_paths:
        evidence_paths.append(report_rel)
    apply_rel = report.get("apply_details_path")
    if isinstance(apply_rel, str) and apply_rel and apply_rel not in evidence_paths:
        evidence_paths.append(apply_rel)
    if github_ops_report_rel and github_ops_report_rel not in evidence_paths and (workspace_root / github_ops_report_rel).exists():
        evidence_paths.append(github_ops_report_rel)
    if isinstance(pr_merge_report_path, str) and pr_merge_report_path and pr_merge_report_path not in evidence_paths:
        evidence_paths.append(pr_merge_report_path)
    if isinstance(memory_health_path, str) and memory_health_path and memory_health_path not in evidence_paths:
        evidence_paths.append(memory_health_path)
    if isinstance(memory_smoke_path, str) and memory_smoke_path and memory_smoke_path not in evidence_paths:
        evidence_paths.append(memory_smoke_path)
    report["evidence_paths"] = evidence_paths
    report["trace_meta"] = build_trace_meta(
        work_item_id=run_id,
        work_item_kind="RUN",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=evidence_paths,
        workspace_root=workspace_root,
    )

    out_json.write_text(_dump_json(report), encoding="utf-8")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    _write_auto_loop_apply_details(
        workspace_root=workspace_root,
        auto_loop_report=report,
        auto_loop_rel=_rel_path(workspace_root, out_json),
    )

    report["report_path"] = _rel_path(workspace_root, out_json)
    report["report_md_path"] = _rel_path(workspace_root, out_md)
    report["budget_seconds"] = int(budget_seconds) if int(budget_seconds) > 0 else None
    report["decision_inbox_status"] = decision_show.get("status")
    report["bulk_apply_status"] = bulk_res.get("status")
    report["work_intake_status"] = intake_payload.get("status")
    report["airunner_status"] = run_res.get("status")
    release_ok = False
    if lock_res.get("lease_id"):
        release_ok = release_doer_loop_lock(workspace_root=workspace_root, lease_id=str(lock_res.get("lease_id") or ""))
    report["lock_release_ok"] = bool(release_ok)
    return report
