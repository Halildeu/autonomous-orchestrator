from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from src.roadmap.evidence import write_integrity_manifest, write_json, write_text
from src.roadmap.orchestrator_io import write_finish_artifacts, write_finish_preview_and_analysis
from src.roadmap.orchestrator_paths import (
    finish_evidence_root,
    finish_run_dir,
    finish_state_path,
    finish_state_schema,
    orchestrator_evidence_root,
    resolve_path,
)
from src.roadmap.orchestrator_runtime import FinishLoopContext, FinishLoopState, run_finish_loop
from src.roadmap.state import (
    bootstrap_completed_milestones,
    bump_attempt,
    clear_backoff,
    clear_quarantine,
    is_in_backoff,
    is_quarantined,
    load_state,
    mark_completed,
    pause_state,
    quarantine_milestone,
    record_last_result,
    resume_state,
    save_state,
    set_backoff,
    set_checkpoint,
    set_current_milestone,
)
from src.roadmap.orchestrator_helpers import *

def pause(*, workspace_root: Path, reason: str, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    workspace_root = resolve_path(core_root, workspace_root)
    state_path = finish_state_path(workspace_root) if state_path is None else state_path.resolve()
    if not state_path.exists():
        return {"status": "FAIL", "error_code": "STATE_NOT_FOUND", "state_path": str(state_path)}

    obj = _load_json(state_path)
    roadmap_path_raw = obj.get("roadmap_path") if isinstance(obj, dict) else None
    if not isinstance(roadmap_path_raw, str) or not roadmap_path_raw:
        return {"status": "FAIL", "error_code": "STATE_INVALID", "state_path": str(state_path)}

    schema_path = core_root / "schemas" / "roadmap-state.schema.json"
    state_res = load_state(
        state_path=state_path,
        schema_path=schema_path,
        roadmap_path=Path(roadmap_path_raw),
        workspace_root=workspace_root,
    )
    state = state_res.state
    pause_state(state, reason=str(reason or "paused"), now=_now_utc())
    clear_backoff(state)
    record_last_result(state, status="FAIL", milestone_id=state.get("current_milestone"), evidence_path=None, error_code="PAUSED")
    save_state(state_path=state_path, state=state)
    return {"status": "OK", "paused": True, "pause_reason": state.get("pause_reason"), "state_path": str(state_path)}


def resume(*, workspace_root: Path, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    workspace_root = resolve_path(core_root, workspace_root)
    state_path = finish_state_path(workspace_root) if state_path is None else state_path.resolve()
    if not state_path.exists():
        return {"status": "FAIL", "error_code": "STATE_NOT_FOUND", "state_path": str(state_path)}

    obj = _load_json(state_path)
    roadmap_path_raw = obj.get("roadmap_path") if isinstance(obj, dict) else None
    if not isinstance(roadmap_path_raw, str) or not roadmap_path_raw:
        return {"status": "FAIL", "error_code": "STATE_INVALID", "state_path": str(state_path)}

    schema_path = core_root / "schemas" / "roadmap-state.schema.json"
    state_res = load_state(
        state_path=state_path,
        schema_path=schema_path,
        roadmap_path=Path(roadmap_path_raw),
        workspace_root=workspace_root,
    )
    state = state_res.state
    resume_state(state)
    clear_backoff(state)
    save_state(state_path=state_path, state=state)
    return {"status": "OK", "paused": False, "state_path": str(state_path)}


def finish(
    *,
    roadmap_path: Path,
    workspace_root: Path,
    max_minutes: int = 120,
    sleep_seconds: int = 120,
    max_steps_per_iteration: int = 3,
    auto_apply_chg: bool = False,
) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = resolve_path(core_root, roadmap_path)
    workspace_root = resolve_path(core_root, workspace_root)

    state_path = finish_state_path(workspace_root)
    state_schema = finish_state_schema(core_root)

    evidence_root = finish_evidence_root(core_root)
    evidence_root.mkdir(parents=True, exist_ok=True)

    core_git_baseline = _git_status_porcelain(core_root)

    start_monotonic = time.monotonic()
    deadline_seconds = max(0, int(max_minutes)) * 60

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    state = state_res.state
    state_before = json.loads(json.dumps(state))

    actions_file = _actions_path(workspace_root)
    actions_reg = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)

    drift_info = _detect_roadmap_drift_and_update_state(
        state=state,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        roadmap_obj=roadmap_obj,
        actions_reg=actions_reg,
    )
    save_state(state_path=state_path, state=state)

    # Bootstrap state deterministically from workspace artifacts (same as follow).
    completed = state.get("completed_milestones", [])
    if not bool(state.get("bootstrapped", False)) or not isinstance(completed, list) or not completed:
        bootstrap_completed_milestones(state=state, workspace_root=workspace_root)
        save_state(state_path=state_path, state=state)
    run_id = _mk_finish_run_id(roadmap_path=roadmap_path, workspace_root=workspace_root, state_before=state_before)
    run_dir = finish_run_dir(evidence_root, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    actions_file = _actions_path(workspace_root)
    actions_before = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    # Ensure the action register exists even if the run terminates early.
    _atomic_write_json(actions_file, actions_before)
    _atomic_write_json(run_dir / "actions_before.json", actions_before)

    iterations: list[dict[str, Any]] = []
    logs: list[str] = []
    chg_generated: list[str] = []
    script_budget_status: str | None = None
    quality_gate_status: str | None = None
    harvest_status: str | None = None
    ops_index_status: str | None = None
    advisor_status: str | None = None
    autopilot_readiness_status: str | None = None
    system_status_status: str | None = None
    system_status_snapshot_before: dict[str, Any] | None = None
    promotion_status: str | None = None
    debt_auto_applied = False
    artifact_completeness: dict[str, Any] | None = None
    pack_conflict_blocked = False
    pack_conflict_report_path = ""
    smoke_drift_minimal = os.environ.get("SMOKE_DRIFT_MINIMAL") == "1"
    debt_policy = _load_debt_policy(core_root=core_root, workspace_root=workspace_root)
    core_policy = _load_core_immutability_policy(core_root=core_root, workspace_root=workspace_root)
    auto_apply_remaining = (
        debt_policy.max_auto_apply_per_finish
        if debt_policy.enabled and debt_policy.mode == "safe_apply"
        else 0
    )
    skipped_ingest = [
        "script_budget",
        "quality_gate",
        "ops_index",
        "harvest",
        "artifact_pointer",
        "advisor",
        "autopilot_readiness",
        "system_status",
        "artifact_completeness",
    ] if smoke_drift_minimal else []

    status_payload: dict[str, Any] = status(roadmap_path=roadmap_path, workspace_root=workspace_root, state_path=state_path)
    next_mid = status_payload.get("next_milestone") if isinstance(status_payload, dict) else None

    logs.append(f"roadmap-finish start roadmap={roadmap_path} workspace={workspace_root}\n")
    if bool(state.get("paused", False)):
        logs.append("PAUSED\n")
        out = {
            "status": "DISABLED",
            "next_milestone": next_mid,
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "error_code": "PAUSED",
        }
        write_json(run_dir / "input.json", {"roadmap": str(roadmap_path), "workspace_root": str(workspace_root)})
        write_json(run_dir / "output.json", out)
        write_json(run_dir / "state_before.json", state_before)
        write_json(run_dir / "state_after.json", state)
        write_text(run_dir / "logs.txt", "".join(logs))
        write_integrity_manifest(run_dir)
        return {**out, "evidence": [str(run_dir.relative_to(core_root))]}
    stop_status: str | None = None
    stop_code: str | None = None

    def _auto_apply_chg_for_milestone(milestone_id: str) -> str | None:
        changes_dir = core_root / "roadmaps" / "SSOT" / "changes"
        changes_dir.mkdir(parents=True, exist_ok=True)
        today = _now_utc().strftime("%Y%m%d")
        existing = sorted([p for p in changes_dir.glob(f"CHG-{today}-*.json") if p.is_file()])
        seq = len(existing) + 1
        change_id = f"CHG-{today}-{seq:03d}"
        change_path = changes_dir / f"{change_id}.json"
        change_obj = {
            "change_id": change_id,
            "version": "v1",
            "type": "modify",
            "risk_level": "low",
            "target": {"milestone_id": milestone_id},
            "rationale": "Auto-generated by roadmap-finish (v0.2) from action register warnings.",
            "patches": [
                {
                    "op": "append_milestone_note",
                    "milestone_id": milestone_id,
                    "note": "AUTO_CHG: review action register warnings",
                }
            ],
            "gates": ["python ci/validate_schemas.py", "python -m src.ops.manage smoke --level fast"],
        }
        _atomic_write_json(change_path, change_obj)
        return str(change_path.relative_to(core_root))

    # Always ingest Script Budget debt into the workspace Action Register (no network, deterministic).
    if not smoke_drift_minimal:
        script_budget_status, script_budget_report = _run_script_budget_checker(core_root=core_root)
        write_json(run_dir / "script_budget_report.json", script_budget_report)
        sb_actions = _script_budget_actions_from_report(script_budget_report)
        if script_budget_status == "OK":
            # Prefer history: mark any previous SCRIPT_BUDGET items resolved instead of deleting.
            reg0 = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            actions0 = reg0.get("actions")
            if isinstance(actions0, list):
                for a in actions0:
                    if not isinstance(a, dict):
                        continue
                    if a.get("source") == "SCRIPT_BUDGET" or a.get("kind") == "SCRIPT_BUDGET":
                        a["resolved"] = True
            _atomic_write_json(actions_file, reg0)
        elif sb_actions:
            reg0 = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            _upsert_actions(reg0, sb_actions)
            _atomic_write_json(actions_file, reg0)

    # Self-healing (v0.1): resolve stale PLACEHOLDER_MILESTONE actions based on the current roadmap definition.
    placeholder_milestones = _placeholder_milestones_from_roadmap(roadmap_obj=roadmap_obj)
    roadmap_milestones = set(str(x) for x in roadmap_ids)
    supported_step_types = _supported_step_types(core_root=core_root)
    reg_ph = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
    if _self_heal_placeholder_actions(
        actions_reg=reg_ph,
        placeholder_milestones=placeholder_milestones,
        roadmap_milestones=roadmap_milestones,
    ):
        _atomic_write_json(actions_file, reg_ph)
    cleanup_report = _self_heal_unknown_step_actions(
        actions_reg=reg_ph,
        supported_types=supported_step_types,
        roadmap_milestones=roadmap_milestones,
        completed_milestones=set(
            str(x) for x in (state.get("completed_milestones") or []) if isinstance(x, str)
        ),
    )
    if cleanup_report.get("changed"):
        _atomic_write_json(actions_file, reg_ph)
    write_json(run_dir / "stale_action_cleanup_report.json", cleanup_report)

    if not smoke_drift_minimal and script_budget_status == "FAIL":
        stop_status = "BLOCKED"
        stop_code = "SCRIPT_BUDGET_HARD_FAIL"
        logs.append("SCRIPT_BUDGET_HARD_FAIL\n")

    if not smoke_drift_minimal and stop_status is None:
        enabled, checks = _load_artifact_completeness_policy(core_root=core_root, workspace_root=workspace_root)
        if enabled:
            missing_before = _artifact_missing(checks=checks, workspace_root=workspace_root)
            attempted: list[str] = []
            healed_ids: set[str] = set()
            still_missing = list(missing_before)
            pack_derived_milestones = {"M2.5", "M3", "M9.2", "M9.3"}
            pack_related_missing = [
                item
                for item in missing_before
                if str(item.get("owner_milestone") or "") in pack_derived_milestones
            ]
            pack_drift_detected = False
            pack_sha_map = _pack_manifest_sha_map(core_root, workspace_root)
            pack_list_sha = _pack_list_sha(pack_sha_map)
            cursor_path = workspace_root / ".cache" / "index" / "pack_index_cursor.v1.json"
            if pack_list_sha and cursor_path.exists():
                try:
                    cursor_obj = _load_json(cursor_path)
                    last_sha = cursor_obj.get("last_pack_list_sha256") if isinstance(cursor_obj, dict) else None
                    if isinstance(last_sha, str) and last_sha and last_sha != pack_list_sha:
                        pack_drift_detected = True
                except Exception:
                    pack_drift_detected = True

            reg_ac = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            actions_changed = False
            if missing_before:
                _upsert_actions(reg_ac, [_artifact_missing_action(item) for item in missing_before])
                actions_changed = True

            pack_validation_obj: dict[str, Any] | None = None
            if pack_related_missing or pack_drift_detected:
                pack_validation_obj, report_path, rc = _run_pack_validation(
                    core_root=core_root,
                    workspace_root=workspace_root,
                    logs=logs,
                )
                pack_conflict_report_path = report_path
                if pack_validation_obj is not None:
                    write_json(run_dir / "pack_validation_report_snapshot.json", pack_validation_obj)
                pack_validation_status = (
                    pack_validation_obj.get("status") if isinstance(pack_validation_obj, dict) else None
                )
                hard_conflicts = (
                    pack_validation_obj.get("hard_conflicts") if isinstance(pack_validation_obj, dict) else None
                )
                soft_conflicts = (
                    pack_validation_obj.get("soft_conflicts") if isinstance(pack_validation_obj, dict) else None
                )
                hard_list = hard_conflicts if isinstance(hard_conflicts, list) else []
                soft_list = soft_conflicts if isinstance(soft_conflicts, list) else []
                if rc != 0 or pack_validation_status == "FAIL":
                    pack_conflict_blocked = True
                    _upsert_actions(
                        reg_ac,
                        [
                            _pack_conflict_action(
                                kind="PACK_CONFLICT",
                                severity="FAIL",
                                report_path=report_path,
                                conflicts=hard_list,
                            )
                        ],
                    )
                    actions_changed = True
                elif soft_list:
                    _upsert_actions(
                        reg_ac,
                        [
                            _pack_conflict_action(
                                kind="PACK_SOFT_CONFLICT",
                                severity="WARN",
                                report_path=report_path,
                                conflicts=soft_list,
                            )
                        ],
                    )
                    actions_changed = True

            if actions_changed:
                _atomic_write_json(actions_file, reg_ac)

            _MILESTONE_TOPO = {"M2.5": 1, "M3": 2, "M3.5": 3, "M6.6": 4, "M6.7": 5, "M7": 6, "M8": 7, "M8.1": 8}
            heal_milestones = sorted(
                {
                    str(item.get("owner_milestone") or "")
                    for item in missing_before
                    if item.get("auto_heal")
                },
                key=lambda m: _MILESTONE_TOPO.get(m, 99),
            )
            if pack_conflict_blocked and heal_milestones:
                heal_milestones = [m for m in heal_milestones if m not in pack_derived_milestones]
            heal_milestones = [m for m in heal_milestones if m]

            if heal_milestones:
                try:
                    from src.roadmap.executor import apply_roadmap
                except Exception as e:
                    logs.append("ARTIFACT_AUTOHEAL_IMPORT_FAILED " + str(e)[:200] + "\n")
                    heal_milestones = []
                for mid in heal_milestones:
                    if deadline_seconds and (time.monotonic() - start_monotonic) > deadline_seconds:
                        break
                    try:
                        apply_roadmap(
                            roadmap_path=roadmap_path,
                            core_root=core_root,
                            workspace_root=workspace_root,
                            cache_root=core_root / ".cache",
                            evidence_root=core_root / "evidence" / "roadmap",
                            dry_run=False,
                            dry_run_mode="simulate",
                            milestone_ids=[mid],
                        )
                        attempted.append(mid)
                    except Exception as e:
                        logs.append("ARTIFACT_AUTOHEAL_FAILED " + str(e)[:200] + "\n")

                missing_after = _artifact_missing(checks=checks, workspace_root=workspace_root)
                missing_after_ids = {str(item.get("id") or "") for item in missing_after}
                for item in missing_before:
                    item_id = str(item.get("id") or "")
                    if item_id and item_id not in missing_after_ids:
                        healed_ids.add(item_id)
                still_missing = missing_after

                if still_missing:
                    reg_ac = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
                    for item in still_missing:
                        if item.get("auto_heal") and str(item.get("owner_milestone") or "") in attempted:
                            _upsert_actions(reg_ac, [_artifact_heal_failed_action(item)])
                    _atomic_write_json(actions_file, reg_ac)

            reg_ac = _load_action_register(actions_file, roadmap_path=roadmap_path, workspace_root=workspace_root)
            missing_reconcile = _reconcile_artifact_missing_actions(actions_reg=reg_ac, current_missing=still_missing)
            if missing_reconcile.get("changed"):
                _atomic_write_json(actions_file, reg_ac)
            write_json(run_dir / "artifact_missing_action_reconcile_report.json", missing_reconcile)

            artifact_completeness = {
                "missing": missing_before,
                "healed": sorted(healed_ids),
                "still_missing": still_missing,
                "attempted_milestones": attempted,
                "pack_conflict_blocked": pack_conflict_blocked,
                "pack_conflict_report_path": pack_conflict_report_path,
                "missing_action_reconcile": missing_reconcile,
            }
            write_json(run_dir / "artifact_completeness_report.json", artifact_completeness)

            if any(item.get("severity") == "block" for item in still_missing):
                stop_status = "BLOCKED"
                stop_code = "DERIVED_ARTIFACT_BLOCKED"
                logs.append("DERIVED_ARTIFACT_BLOCKED\n")


    loop_ctx = FinishLoopContext(
        core_root=core_root,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        state_path=state_path,
        state_schema=state_schema,
        roadmap_obj=roadmap_obj,
        roadmap_ids=roadmap_ids,
        run_dir=run_dir,
        actions_file=actions_file,
        state_before=state_before,
        core_policy=core_policy,
        core_git_baseline=core_git_baseline,
        debt_policy=debt_policy,
        start_monotonic=start_monotonic,
        deadline_seconds=deadline_seconds,
        max_steps_per_iteration=max_steps_per_iteration,
        sleep_seconds=sleep_seconds,
        auto_apply_chg=auto_apply_chg,
        smoke_drift_minimal=smoke_drift_minimal,
        skipped_ingest=skipped_ingest,
        drift_info=drift_info,
        artifact_completeness=artifact_completeness,
        pack_conflict_blocked=pack_conflict_blocked,
        pack_conflict_report_path=pack_conflict_report_path,
    )
    loop_state = FinishLoopState(
        roadmap_state=state,
        iterations=iterations,
        logs=logs,
        chg_generated=chg_generated,
        script_budget_status=script_budget_status,
        quality_gate_status=quality_gate_status,
        harvest_status=harvest_status,
        ops_index_status=ops_index_status,
        advisor_status=advisor_status,
        autopilot_readiness_status=autopilot_readiness_status,
        system_status_status=system_status_status,
        system_status_snapshot_before=system_status_snapshot_before,
        promotion_status=promotion_status,
        debt_auto_applied=debt_auto_applied,
        auto_apply_remaining=auto_apply_remaining,
        stop_status=stop_status,
        stop_code=stop_code,
    )
    loop_res = run_finish_loop(
        ctx=loop_ctx,
        state=loop_state,
        preview_writer=write_finish_preview_and_analysis,
        status_func=status,
        follow_func=follow,
        script_budget_runner=lambda: _run_script_budget_checker(core_root=core_root),
        auto_apply_chg_handler=_auto_apply_chg_for_milestone,
    )

    out = loop_res.out
    write_finish_artifacts(
        core_root=core_root,
        run_dir=run_dir,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        state_path=state_path,
        state_before=state_before,
        state_after=loop_res.state_after,
        out=out,
        iterations=loop_res.iterations,
        logs=loop_res.logs,
        max_minutes=max_minutes,
        sleep_seconds=sleep_seconds,
        max_steps_per_iteration=max_steps_per_iteration,
        auto_apply_chg=auto_apply_chg,
    )

    return {**out, "evidence": [str(run_dir.relative_to(core_root))]}


def status(*, roadmap_path: Path, workspace_root: Path, state_path: Path | None = None) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = resolve_path(core_root, roadmap_path)
    workspace_root = resolve_path(core_root, workspace_root)
    state_path = finish_state_path(workspace_root) if state_path is None else state_path.resolve()
    state_schema = finish_state_schema(core_root)

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    st = state_res.state
    completed = st.get("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []

    next_mid = _next_milestone(roadmap_ids, completed)
    return {
        "status": "OK",
        "bootstrapped": bool(st.get("bootstrapped", False)),
        "next_milestone": next_mid,
        "completed_milestones": completed,
        "completed_count": len(completed),
        "quarantine": st.get("quarantine"),
        "backoff": st.get("backoff"),
        "last_result": st.get("last_result"),
        "state_path": str(state_path),
    }


def follow(
    *,
    roadmap_path: Path,
    workspace_root: Path,
    until: str | None = None,
    max_steps: int = 1,
    dry_run_mode: str = "readonly",
    no_apply: bool = False,
    state_path: Path | None = None,
    force_unquarantine: bool = False,
) -> dict[str, Any]:
    core_root = _core_root()
    roadmap_path = resolve_path(core_root, roadmap_path)
    workspace_root = resolve_path(core_root, workspace_root)
    state_path = finish_state_path(workspace_root) if state_path is None else state_path.resolve()
    state_schema = finish_state_schema(core_root)

    evidence_root = orchestrator_evidence_root(core_root)

    evidence_paths: list[str] = []
    logs_parts: list[str] = []

    def finalize(*, out: dict[str, Any], state_before: dict[str, Any], state_after: dict[str, Any]) -> dict[str, Any]:
        out.setdefault("bootstrapped", bool(state_after.get("bootstrapped", False)))
        run_id = _mk_orchestrator_run_id(
            roadmap_path=roadmap_path,
            workspace_root=workspace_root,
            next_milestone=str(out.get("next_milestone") or ""),
            state_before=state_before,
        )
        run_dir = evidence_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            run_dir / "input.json",
            {
                "roadmap": str(roadmap_path),
                "workspace_root": str(workspace_root),
                "state_path": str(state_path),
                "requested": {
                    "until": until,
                    "max_steps": int(max_steps),
                    "dry_run_mode": dry_run_mode,
                    "no_apply": bool(no_apply),
                    "force_unquarantine": bool(force_unquarantine),
                },
            },
        )
        write_json(run_dir / "state_before.json", state_before)
        write_json(run_dir / "state_after.json", state_after)
        write_json(run_dir / "output.json", out)
        write_text(run_dir / "logs.txt", "".join(logs_parts))
        write_integrity_manifest(run_dir)

        out["evidence"] = list(out.get("evidence") or []) + [str(run_dir.relative_to(core_root))]
        return out

    if os.environ.get("AUTOPILOT_DISABLED") == "1" or os.environ.get("ORCH_AUTOPILOT_DISABLED") == "1":
        logs_parts.append("AUTOPILOT_DISABLED=1\n")
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": [],
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "AUTOPILOT_DISABLED",
        }
        return finalize(out=out, state_before={}, state_after={})

    if _load_governor_global_mode(core_root) == "report_only":
        logs_parts.append("governor.global_mode=report_only\n")
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": [],
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "GOVERNOR_REPORT_ONLY",
        }
        return finalize(out=out, state_before={}, state_after={})

    roadmap_obj = _load_and_validate_roadmap(core_root, roadmap_path)
    roadmap_ids = _roadmap_milestones(roadmap_obj)
    if until is not None and until not in set(roadmap_ids):
        raise ValueError("MILESTONE_NOT_FOUND: " + str(until))

    state_res = load_state(
        state_path=state_path,
        schema_path=state_schema,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
    )
    state = state_res.state
    state_before = json.loads(json.dumps(state))

    # Drift detection (v0.4): if the roadmap changed, update state hashes and optionally re-run stale milestones.
    actions_reg = None
    actions_path = _actions_path(workspace_root)
    if actions_path.exists():
        actions_reg = _load_action_register(actions_path, roadmap_path=roadmap_path, workspace_root=workspace_root)
    drift_info = _detect_roadmap_drift_and_update_state(
        state=state,
        roadmap_path=roadmap_path,
        workspace_root=workspace_root,
        roadmap_obj=roadmap_obj,
        actions_reg=actions_reg,
    )
    save_state(state_path=state_path, state=state)

    now = _now_utc()
    if force_unquarantine:
        clear_quarantine(state)
        clear_backoff(state)

    if bool(state.get("paused", False)):
        reason = state.get("pause_reason") if isinstance(state.get("pause_reason"), str) else None
        logs_parts.append(f"PAUSED reason={reason or 'paused'}\n")
        clear_backoff(state)
        record_last_result(state, status="FAIL", milestone_id=None, evidence_path=None, error_code="PAUSED")
        save_state(state_path=state_path, state=state)
        out = {
            "status": "DISABLED",
            "next_milestone": None,
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": "PAUSED",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    # Fail-closed: if we are in quarantine/backoff, do not attempt anything.
    if is_quarantined(state, now=now):
        q = state.get("quarantine", {})
        logs_parts.append("QUARANTINED\n")
        out = {
            "status": "BLOCKED",
            "next_milestone": q.get("milestone"),
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": q.get("until"),
            "error_code": "QUARANTINED",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    if is_in_backoff(state, now=now):
        b = state.get("backoff", {})
        logs_parts.append("BACKOFF\n")
        out = {
            "status": "BLOCKED",
            "next_milestone": state.get("current_milestone"),
            "completed": state.get("completed_milestones", []),
            "evidence": [],
            "backoff_seconds": b.get("seconds"),
            "quarantine_until": None,
            "error_code": "BACKOFF",
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    baseline_git = _git_status_porcelain(core_root)
    if baseline_git is None:
        raise ValueError("READONLY_MODE_REQUIRES_GIT")
    baseline_ws = _snapshot_tree(
        workspace_root,
        ignore_prefixes=[
            ".cache",
            "evidence",
            "dlq",
            "__pycache__",
        ],
    )

    completed = state.get("completed_milestones", [])
    if not isinstance(completed, list):
        completed = []

    # Bootstrap from workspace artifacts when state is empty or not bootstrapped yet.
    if not bool(state.get("bootstrapped", False)) or not completed:
        warnings = bootstrap_completed_milestones(state=state, workspace_root=workspace_root)
        if warnings:
            logs_parts.append("BOOTSTRAP_WARNINGS: " + "; ".join(warnings) + "\n")
        save_state(state_path=state_path, state=state)
        completed = state.get("completed_milestones", [])
        if not isinstance(completed, list):
            completed = []
    if until is not None and until in set(str(x) for x in completed):
        logs_parts.append("DONE (until already completed)\n")
        out = {
            "status": "DONE",
            "next_milestone": None,
            "completed": completed,
            "evidence": [],
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": None,
        }
        return finalize(out=out, state_before=state_before, state_after=state)

    out: dict[str, Any] = {
        "status": "DONE",
        "next_milestone": None,
        "completed": completed,
        "evidence": evidence_paths,
        "backoff_seconds": None,
        "quarantine_until": None,
        "error_code": None,
        "roadmap_sha256": drift_info.get("roadmap_sha256"),
        "drift_detected": drift_info.get("drift_detected"),
        "stale_milestones": drift_info.get("stale_milestones"),
        "stale_reset_milestones": drift_info.get("stale_reset_milestones"),
    }

    for _ in range(max(1, int(max_steps))):
        next_mid = _next_milestone(roadmap_ids, completed)
        if next_mid is None:
            break

        # ISO-core preflight (v0.1): if roadmap says ISO is required, ensure it exists before running non-ISO milestones.
        iso_required = bool(roadmap_obj.get("iso_core_required", False))
        if iso_required and next_mid != "M1" and not _check_iso_core_presence(workspace_root):
            clear_backoff(state)
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code="ISO_MISSING")
            save_state(state_path=state_path, state=state)
            out = {
                "status": "ISO_MISSING",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": "ISO_MISSING",
            }
            break

        set_current_milestone(state, next_mid)
        attempt = bump_attempt(state, next_mid)
        set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=None)
        save_state(state_path=state_path, state=state)

        env = os.environ.copy()
        env["ORCH_WORKSPACE_ROOT"] = str(workspace_root)
        # Avoid recursion when gates run smoke_test.py.
        env["ORCH_ROADMAP_ORCHESTRATOR"] = "1"

        logs_parts.append(f"== milestone {next_mid} attempt {attempt} ==\n")

        # 1) Readonly dry-run apply
        argv_ro = [
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            str(roadmap_path),
            "--milestone",
            next_mid,
            "--workspace-root",
            str(workspace_root),
            "--dry-run",
            "true",
            "--dry-run-mode",
            str(dry_run_mode),
        ]
        res_ro = _run_cmd(core_root, argv_ro, env=env)
        logs_parts.append(res_ro.stdout)
        if res_ro.stderr:
            logs_parts.append("\n" + res_ro.stderr)
        ro_obj: dict[str, Any] = {}
        try:
            ro_obj = json.loads(res_ro.stdout.strip() or "{}")
        except Exception:
            ro_obj = {}
        ev_ro = ro_obj.get("evidence_path") if isinstance(ro_obj, dict) else None
        if isinstance(ev_ro, str) and ev_ro:
            evidence_paths.append(ev_ro)

        if res_ro.returncode != 0:
            code = str(ro_obj.get("error_code") or "ROADMAP_APPLY_READONLY_FAILED")
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=code)
            set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": code,
            }
            break

        ok_clean, clean_code = _enforce_readonly_clean(
            core_root=core_root,
            baseline_git_status=baseline_git,
            workspace_root=workspace_root,
            baseline_workspace_snapshot=baseline_ws,
        )
        if not ok_clean:
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=clean_code)
            set_checkpoint(state, current_step_id=f"{next_mid}:READONLY_APPLY", last_completed_step_id=state.get("last_completed_step_id"), last_gate_ok=False)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": clean_code,
            }
            break

        if no_apply:
            clear_backoff(state)
            record_last_result(state, status="OK", milestone_id=next_mid, evidence_path=None, error_code=None)
            set_checkpoint(state, current_step_id=None, last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=True)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "OK",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": None,
            }
            break

        # 2) Apply
        argv_apply = [
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            str(roadmap_path),
            "--milestone",
            next_mid,
            "--workspace-root",
            str(workspace_root),
            "--dry-run",
            "false",
        ]
        set_checkpoint(state, current_step_id=f"{next_mid}:APPLY", last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=None)
        save_state(state_path=state_path, state=state)
        res_apply = _run_cmd(core_root, argv_apply, env=env)
        logs_parts.append(res_apply.stdout)
        if res_apply.stderr:
            logs_parts.append("\n" + res_apply.stderr)
        apply_obj: dict[str, Any] = {}
        try:
            apply_obj = json.loads(res_apply.stdout.strip() or "{}")
        except Exception:
            apply_obj = {}
        ev_apply = apply_obj.get("evidence_path") if isinstance(apply_obj, dict) else None
        if isinstance(ev_apply, str) and ev_apply:
            evidence_paths.append(ev_apply)

        if res_apply.returncode != 0:
            code = str(apply_obj.get("error_code") or "ROADMAP_APPLY_FAILED")
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=code)
            set_checkpoint(state, current_step_id=f"{next_mid}:APPLY", last_completed_step_id=f"{next_mid}:READONLY_APPLY", last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": code,
            }
            break

        # After apply, snapshot the workspace state so post-gates can enforce "no further writes".
        baseline_ws = _snapshot_tree(
            workspace_root,
            ignore_prefixes=[
                ".cache",
                "evidence",
                "dlq",
                "__pycache__",
            ],
        )

        # 3) Post gates (readonly verification style)
        set_checkpoint(state, current_step_id=f"{next_mid}:POST_GATES", last_completed_step_id=f"{next_mid}:APPLY", last_gate_ok=None)
        save_state(state_path=state_path, state=state)
        gate_env = env.copy()
        gate_env["ORCH_ROADMAP_ORCHESTRATOR"] = "1"
        # Avoid recursion + keep it cheaper: post-gate smoke should not re-run roadmap-runner smoke sections.
        gate_env["ORCH_ROADMAP_RUNNER"] = "1"
        gate_argvs = [
            [sys.executable, str(core_root / "ci" / "validate_schemas.py")],
            [sys.executable, str(core_root / "smoke_test.py")],
            [sys.executable, "-m", "src.ops.manage", "policy-check", "--source", "fixtures"],
        ]
        gate_failed_code: str | None = None
        for gargv in gate_argvs:
            gres = _run_cmd(core_root, gargv, env=gate_env)
            logs_parts.append(gres.stdout)
            if gres.stderr:
                logs_parts.append("\n" + gres.stderr)
            ok_clean, clean_code = _enforce_readonly_clean(
                core_root=core_root,
                baseline_git_status=baseline_git,
                workspace_root=workspace_root,
                baseline_workspace_snapshot=baseline_ws,
            )
            if not ok_clean:
                gate_failed_code = clean_code
                break
            if gres.returncode != 0:
                gate_failed_code = "POST_GATES_FAILED"
                break

        if gate_failed_code is not None:
            record_last_result(state, status="FAIL", milestone_id=next_mid, evidence_path=None, error_code=gate_failed_code)
            set_checkpoint(state, current_step_id=f"{next_mid}:POST_GATES", last_completed_step_id=f"{next_mid}:APPLY", last_gate_ok=False)
            backoff_seconds = 120 if attempt == 1 else 300 if attempt == 2 else 900
            set_backoff(state, seconds=backoff_seconds, now=now)
            if attempt >= 3:
                quarantine_milestone(state, milestone_id=next_mid, now=now, reason=gate_failed_code)
            save_state(state_path=state_path, state=state)
            out = {
                "status": "BLOCKED",
                "next_milestone": next_mid,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": backoff_seconds,
                "quarantine_until": state.get("quarantine", {}).get("until"),
                "error_code": gate_failed_code,
            }
            break

        # Success path: mark completed and move on.
        clear_backoff(state)
        clear_quarantine(state)
        mark_completed(state, next_mid)
        completed = state.get("completed_milestones", completed)
        record_last_result(state, status="OK", milestone_id=next_mid, evidence_path=None, error_code=None)
        set_checkpoint(state, current_step_id=None, last_completed_step_id=f"{next_mid}:POST_GATES", last_gate_ok=True)
        save_state(state_path=state_path, state=state)

        if until is not None and next_mid == until:
            out = {
                "status": "OK",
                "next_milestone": None,
                "completed": completed,
                "evidence": evidence_paths,
                "backoff_seconds": None,
                "quarantine_until": None,
                "error_code": None,
            }
            break

        # Continue loop for --max-steps > 1
        out = {
            "status": "OK",
            "next_milestone": _next_milestone(roadmap_ids, completed),
            "completed": completed,
            "evidence": evidence_paths,
            "backoff_seconds": None,
            "quarantine_until": None,
            "error_code": None,
        }

    if out.get("status") == "DONE":
        out["next_milestone"] = _next_milestone(roadmap_ids, completed)
        out["completed"] = completed

    return finalize(out=out, state_before=state_before, state_after=state)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.roadmap.orchestrator")
    ap.add_argument("--roadmap", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--until", default=None)
    ap.add_argument("--max-steps", type=int, default=1)
    ap.add_argument("--dry-run-mode", default="readonly", choices=["simulate", "readonly"])
    ap.add_argument("--no-apply", default="false", help="true|false (default: false)")
    ap.add_argument("--state-path", default=None, help="Optional explicit state path.")
    ap.add_argument("--force-unquarantine", action="store_true")
    args = ap.parse_args(argv)

    no_apply_raw = str(args.no_apply).strip().lower()
    if no_apply_raw not in {"true", "false"}:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        payload = follow(
            roadmap_path=Path(str(args.roadmap)),
            workspace_root=Path(str(args.workspace_root)),
            until=(str(args.until) if args.until else None),
            max_steps=int(args.max_steps),
            dry_run_mode=str(args.dry_run_mode),
            no_apply=(no_apply_raw == "true"),
            state_path=(Path(str(args.state_path)) if args.state_path else None),
            force_unquarantine=bool(args.force_unquarantine),
        )
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "ORCHESTRATOR_ERROR", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
