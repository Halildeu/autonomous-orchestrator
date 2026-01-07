from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable

from src.roadmap.evidence import write_json, write_text
from src.roadmap.orchestrator_helpers import *
from src.roadmap.state import load_state, mark_completed, record_last_result, save_state
from src.session.context_store import SessionContextError, SessionPaths, load_context


@dataclass
class FinishLoopContext:
    core_root: Path
    roadmap_path: Path
    workspace_root: Path
    state_path: Path
    state_schema: Path
    roadmap_obj: dict[str, Any]
    roadmap_ids: list[str]
    run_dir: Path
    actions_file: Path
    state_before: dict[str, Any]
    core_policy: Any
    core_git_baseline: str | None
    debt_policy: Any
    start_monotonic: float
    deadline_seconds: int
    max_steps_per_iteration: int
    sleep_seconds: int
    auto_apply_chg: bool
    smoke_drift_minimal: bool
    skipped_ingest: list[str]
    drift_info: dict[str, Any]
    artifact_completeness: dict[str, Any] | None
    pack_conflict_blocked: bool
    pack_conflict_report_path: str


@dataclass
class FinishLoopState:
    roadmap_state: dict[str, Any]
    iterations: list[dict[str, Any]]
    logs: list[str]
    chg_generated: list[str]
    script_budget_status: str | None
    quality_gate_status: str | None
    harvest_status: str | None
    ops_index_status: str | None
    advisor_status: str | None
    autopilot_readiness_status: str | None
    system_status_status: str | None
    system_status_snapshot_before: dict[str, Any] | None
    promotion_status: str | None
    debt_auto_applied: bool
    auto_apply_remaining: int
    stop_status: str | None
    stop_code: str | None


@dataclass
class FinishLoopResult:
    out: dict[str, Any]
    iterations: list[dict[str, Any]]
    logs: list[str]
    state_after: dict[str, Any]
    actions_after: dict[str, Any]


def run_finish_loop(
    *,
    ctx: FinishLoopContext,
    state: FinishLoopState,
    preview_writer: Callable[..., tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]],
    status_func: Callable[..., dict[str, Any]],
    follow_func: Callable[..., dict[str, Any]],
    script_budget_runner: Callable[[], tuple[str, dict[str, Any]]],
    auto_apply_chg_handler: Callable[[str], str | None],
) -> FinishLoopResult:
    iterations = state.iterations
    logs = state.logs
    chg_generated = state.chg_generated
    script_budget_status = state.script_budget_status
    quality_gate_status = state.quality_gate_status
    harvest_status = state.harvest_status
    ops_index_status = state.ops_index_status
    advisor_status = state.advisor_status
    autopilot_readiness_status = state.autopilot_readiness_status
    system_status_status = state.system_status_status
    system_status_snapshot_before = state.system_status_snapshot_before
    promotion_status = state.promotion_status
    debt_auto_applied = state.debt_auto_applied
    auto_apply_remaining = state.auto_apply_remaining
    stop_status = state.stop_status
    stop_code = state.stop_code

    roadmap_state = state.roadmap_state
    core_violation_code: str | None = None

    def _enforce_core_clean(*, phase: str) -> tuple[bool, str | None]:
        nonlocal core_violation_code
        ok, code, lines = _core_immutability_check(
            core_root=ctx.core_root,
            policy=ctx.core_policy,
            baseline=ctx.core_git_baseline,
        )
        if ok:
            if _core_unlock_requested(ctx.core_policy) and ctx.core_policy.evidence_required_when_unlocked and lines:
                write_json(ctx.run_dir / "core_dirty_files.json", sorted(lines))
            elif phase == "final":
                write_json(ctx.run_dir / "core_dirty_files.json", [])
            return (True, None)
        paths = _git_status_paths(lines)
        write_json(ctx.run_dir / "core_dirty_files.json", sorted(lines))
        reg_core = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
        _upsert_actions(reg_core, [_core_touched_action(error_code=str(code), paths=paths)])
        _atomic_write_json(ctx.actions_file, reg_core)
        logs.append(f"CORE_WRITE_VIOLATION phase={phase} code={code}\n")
        core_violation_code = str(code) if code else "CORE_WRITE_VIOLATION"
        return (False, core_violation_code)

    while True:
        if stop_status is not None:
            break
        if ctx.deadline_seconds and (time.monotonic() - ctx.start_monotonic) > ctx.deadline_seconds:
            stop_status = "BLOCKED"
            stop_code = "TIME_LIMIT"
            logs.append("TIME_LIMIT\n")
            break

        st = status_func(roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root, state_path=ctx.state_path)
        next_mid = st.get("next_milestone") if isinstance(st, dict) else None
        if next_mid is None:
            stop_status = "DONE"
            break

        slept_for_backoff = False
        for _ in range(max(1, int(ctx.max_steps_per_iteration))):
            if ctx.deadline_seconds and (time.monotonic() - ctx.start_monotonic) > ctx.deadline_seconds:
                stop_status = "BLOCKED"
                stop_code = "TIME_LIMIT"
                logs.append("TIME_LIMIT\n")
                break

            st2 = status_func(roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root, state_path=ctx.state_path)
            next_mid = st2.get("next_milestone") if isinstance(st2, dict) else None
            if next_mid is None:
                stop_status = "DONE"
                break

            milestone_id = str(next_mid)

            # Preview + deep evaluation (saved to evidence).
            try:
                _, preview_obj, new_actions = preview_writer(
                    core_root=ctx.core_root,
                    roadmap_path=ctx.roadmap_path,
                    run_dir=ctx.run_dir,
                    roadmap_obj=ctx.roadmap_obj,
                    milestone_id=milestone_id,
                )
            except Exception as e:
                stop_status = "BLOCKED"
                stop_code = "PREVIEW_FAILED"
                logs.append("PREVIEW_PLAN_FAILED " + str(e)[:300] + "\n")
                break

            iterations.append({"milestone_id": milestone_id, "preview": preview_obj})

            # Action register updates: placeholder/unknown steps + script budget WARN.
            reg = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
            _add_actions(reg, new_actions)
            _atomic_write_json(ctx.actions_file, reg)

            if ctx.auto_apply_chg and new_actions:
                change_rel = auto_apply_chg_handler(milestone_id)
                if change_rel:
                    chg_generated.append(change_rel)

            # Advance exactly one milestone (follow is fail-closed and writes its own evidence).
            res = follow_func(roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root, max_steps=1, dry_run_mode="readonly")
            iterations[-1]["follow"] = res
            logs.append(
                json.dumps({"milestone_id": milestone_id, "follow_status": res.get("status")}, ensure_ascii=False, sort_keys=True)
                + "\n"
            )

            if not ctx.smoke_drift_minimal:
                # Ingest Script Budget after the iteration gates (fail-closed).
                script_budget_status, script_budget_report = script_budget_runner()
                write_json(ctx.run_dir / "script_budget_report.json", script_budget_report)
                iterations[-1]["script_budget_status"] = script_budget_status
                reg_sb = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                sb_actions = _script_budget_actions_from_report(script_budget_report)
                if script_budget_status == "OK":
                    actions_sb = reg_sb.get("actions")
                    if isinstance(actions_sb, list):
                        for a in actions_sb:
                            if not isinstance(a, dict):
                                continue
                            if a.get("source") == "SCRIPT_BUDGET" or a.get("kind") == "SCRIPT_BUDGET":
                                a["resolved"] = True
                else:
                    _upsert_actions(reg_sb, sb_actions)
                _atomic_write_json(ctx.actions_file, reg_sb)

                if script_budget_status == "FAIL":
                    stop_status = "BLOCKED"
                    stop_code = "SCRIPT_BUDGET_HARD_FAIL"
                    logs.append("SCRIPT_BUDGET_HARD_FAIL\n")
                    break

                # Ingest Quality Gate after the iteration gates (fail-closed).
                quality_gate_status, quality_gate_report = _run_quality_gate_checker(
                    core_root=ctx.core_root, workspace_root=ctx.workspace_root
                )
                write_json(ctx.run_dir / "quality_gate_report.json", quality_gate_report)
                iterations[-1]["quality_gate_status"] = quality_gate_status
                reg_qg = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                if quality_gate_status == "OK":
                    actions_qg = reg_qg.get("actions")
                    if isinstance(actions_qg, list):
                        for a in actions_qg:
                            if not isinstance(a, dict):
                                continue
                            if a.get("kind") == "QUALITY_GATE_WARN" or a.get("source") == "QUALITY_GATE":
                                a["resolved"] = True
                elif quality_gate_status == "WARN":
                    action = _quality_gate_warn_action_from_report(quality_gate_report)
                    if action:
                        _upsert_actions(reg_qg, [action])
                else:
                    stop_status = "BLOCKED"
                    stop_code = "QUALITY_GATE_FAIL"
                    logs.append("QUALITY_GATE_FAIL\n")
                    _atomic_write_json(ctx.actions_file, reg_qg)
                    break
                _atomic_write_json(ctx.actions_file, reg_qg)

                # Learning harvest (public candidates, offline, sanitized).
                try:
                    from src.learning.harvest_public_candidates import action_from_harvest_result, run_harvest_for_workspace

                    harvest_res = run_harvest_for_workspace(
                        workspace_root=ctx.workspace_root, core_root=ctx.core_root, dry_run=False
                    )
                except Exception as e:
                    harvest_res = {"status": "FAIL", "error_code": "HARVEST_EXCEPTION", "message": str(e)[:300]}
                harvest_status = str(harvest_res.get("status") or "FAIL")
                iterations[-1]["harvest_status"] = harvest_status
                write_json(ctx.run_dir / "public_candidates_report.json", harvest_res)
                out_raw = harvest_res.get("out") if isinstance(harvest_res, dict) else None
                if isinstance(out_raw, str) and out_raw:
                    out_path = Path(out_raw)
                    if out_path.exists():
                        try:
                            write_json(ctx.run_dir / "public_candidates_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass
                reg_h = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                action = action_from_harvest_result(harvest_res) if isinstance(harvest_res, dict) else None
                if isinstance(action, dict):
                    _upsert_actions(reg_h, [action])
                _atomic_write_json(ctx.actions_file, reg_h)
                if harvest_status == "FAIL":
                    stop_status = "BLOCKED"
                    stop_code = "HARVEST_PUBLIC_CANDIDATES_FAIL"
                    logs.append("HARVEST_PUBLIC_CANDIDATES_FAIL\n")
                    break

                # Ops index (run_index + dlq_index) after iteration gates.
                ops_index_status, ops_index_report = _run_ops_index_builder(
                    core_root=ctx.core_root, workspace_root=ctx.workspace_root
                )
                write_json(ctx.run_dir / "ops_index_report.json", ops_index_report)
                iterations[-1]["ops_index_status"] = ops_index_status
                out_paths = ops_index_report.get("out_paths") if isinstance(ops_index_report, dict) else None
                if isinstance(out_paths, list):
                    for raw in out_paths:
                        if not isinstance(raw, str) or not raw:
                            continue
                        p = Path(raw)
                        if not p.exists():
                            continue
                        name = p.name
                        if "run_index" in name:
                            try:
                                write_json(ctx.run_dir / "run_index_snapshot.json", _load_json(p))
                            except Exception:
                                pass
                        elif "dlq_index" in name:
                            try:
                                write_json(ctx.run_dir / "dlq_index_snapshot.json", _load_json(p))
                            except Exception:
                                pass
                reg_ops = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                if ops_index_status == "OK":
                    actions_ops = reg_ops.get("actions")
                    if isinstance(actions_ops, list):
                        for a in actions_ops:
                            if not isinstance(a, dict):
                                continue
                            if a.get("kind") == "OPS_INDEX_WARN" or a.get("source") == "OPS_INDEX":
                                a["resolved"] = True
                elif ops_index_status == "WARN":
                    action = _ops_index_action_from_report(ops_index_report)
                    if action:
                        _upsert_actions(reg_ops, [action])
                else:
                    stop_status = "BLOCKED"
                    stop_code = "OPS_INDEX_FAIL"
                    logs.append("OPS_INDEX_FAIL\n")
                    _atomic_write_json(ctx.actions_file, reg_ops)
                    break
                _atomic_write_json(ctx.actions_file, reg_ops)

                # Advisor suggestions (suggest-only, offline).
                try:
                    from src.learning.advisor_suggest import action_from_advisor_result, run_advisor_for_workspace

                    advisor_res = run_advisor_for_workspace(
                        workspace_root=ctx.workspace_root, core_root=ctx.core_root, dry_run=False
                    )
                except Exception as e:
                    advisor_res = {
                        "status": "FAIL",
                        "error_code": "ADVISOR_EXCEPTION",
                        "message": str(e)[:300],
                        "on_fail": "warn",
                    }
                advisor_status = str(advisor_res.get("status") or "FAIL")
                iterations[-1]["advisor_status"] = advisor_status
                write_json(ctx.run_dir / "advisor_suggestions_report.json", advisor_res)
                advisor_out = advisor_res.get("out") if isinstance(advisor_res, dict) else None
                if isinstance(advisor_out, str) and advisor_out:
                    out_path = Path(advisor_out)
                    if out_path.exists():
                        try:
                            write_json(ctx.run_dir / "advisor_suggestions_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass

                reg_adv = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                adv_action = action_from_advisor_result(advisor_res) if isinstance(advisor_res, dict) else None
                if isinstance(adv_action, dict):
                    _upsert_actions(reg_adv, [adv_action])
                _atomic_write_json(ctx.actions_file, reg_adv)

                if advisor_status == "FAIL" and advisor_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "ADVISOR_FAIL"
                    logs.append("ADVISOR_FAIL\n")
                    break

                # Autopilot readiness (offline, deterministic).
                try:
                    from src.autopilot.readiness_report import action_from_readiness_result, run_readiness_for_workspace

                    readiness_res = run_readiness_for_workspace(
                        workspace_root=ctx.workspace_root, core_root=ctx.core_root, dry_run=False
                    )
                except Exception as e:
                    readiness_res = {
                        "status": "FAIL",
                        "error_code": "AUTOPILOT_READINESS_EXCEPTION",
                        "message": str(e)[:300],
                        "on_fail": "warn",
                    }
                autopilot_readiness_status = str(readiness_res.get("status") or "FAIL")
                iterations[-1]["autopilot_readiness_status"] = autopilot_readiness_status
                write_json(ctx.run_dir / "autopilot_readiness_report.json", readiness_res)
                readiness_out = readiness_res.get("out") if isinstance(readiness_res, dict) else None
                if isinstance(readiness_out, str) and readiness_out:
                    out_path = Path(readiness_out)
                    if out_path.exists():
                        try:
                            write_json(ctx.run_dir / "autopilot_readiness_snapshot.json", _load_json(out_path))
                        except Exception:
                            pass

                reg_ready = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                ready_action = action_from_readiness_result(readiness_res) if isinstance(readiness_res, dict) else None
                if isinstance(ready_action, dict):
                    _upsert_actions(reg_ready, [ready_action])
                _atomic_write_json(ctx.actions_file, reg_ready)

                if autopilot_readiness_status == "FAIL" and readiness_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "AUTOPILOT_READINESS_FAIL"
                    logs.append("AUTOPILOT_READINESS_FAIL\n")
                    break

                # System status report (JSON + Markdown).
                try:
                    from src.ops.system_status_report import action_from_system_status_result, run_system_status

                    system_res = run_system_status(
                        workspace_root=ctx.workspace_root, core_root=ctx.core_root, dry_run=False
                    )
                except Exception as e:
                    system_res = {
                        "status": "FAIL",
                        "error_code": "SYSTEM_STATUS_EXCEPTION",
                        "message": str(e)[:300],
                        "on_fail": "warn",
                    }
                system_status_status = str(system_res.get("status") or "FAIL")
                iterations[-1]["system_status_status"] = system_status_status
                write_json(ctx.run_dir / "system_status_report.json", system_res)
                system_status_snapshot_before = _system_status_snapshot_from_result(system_res)

                out_json = system_res.get("out_json") if isinstance(system_res, dict) else None
                if isinstance(out_json, str) and out_json:
                    json_path = Path(out_json)
                    if json_path.exists():
                        try:
                            write_json(ctx.run_dir / "system_status_snapshot.json", _load_json(json_path))
                        except Exception:
                            pass
                out_md = system_res.get("out_md") if isinstance(system_res, dict) else None
                if isinstance(out_md, str) and out_md:
                    md_path = Path(out_md)
                    if md_path.exists():
                        try:
                            write_text(ctx.run_dir / "system_status_snapshot.md", md_path.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                reg_sys = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
                sys_action = action_from_system_status_result(system_res) if isinstance(system_res, dict) else None
                if isinstance(sys_action, dict):
                    _upsert_actions(reg_sys, [sys_action])
                _atomic_write_json(ctx.actions_file, reg_sys)

                if system_status_status == "FAIL" and system_res.get("on_fail") == "block":
                    stop_status = "BLOCKED"
                    stop_code = "SYSTEM_STATUS_FAIL"
                    logs.append("SYSTEM_STATUS_FAIL\n")
                    break

                # Debt drafting (suggest-only, workspace-only).
                if not ctx.smoke_drift_minimal:
                    include_repo_suggest = _system_status_include_repo_hygiene_suggestions(
                        core_root=ctx.core_root, workspace_root=ctx.workspace_root
                    )
                    debt_auto_applied = False
                    debt_auto_applied_chg: Path | None = None
                    if ctx.debt_policy.enabled or include_repo_suggest:
                        try:
                            from src.ops.debt_drafter import action_from_debt_draft_result, run_debt_drafter

                            max_items = ctx.debt_policy.max_items if ctx.debt_policy.enabled else 3
                            max_items = min(max_items if max_items > 0 else 3, 3)
                            outdir = Path(ctx.debt_policy.outdir)
                            if not outdir.is_absolute():
                                outdir = (ctx.workspace_root / outdir).resolve()
                            debt_res = run_debt_drafter(
                                workspace_root=ctx.workspace_root,
                                core_root=ctx.core_root,
                                outdir=outdir,
                                max_items=max_items,
                            )
                        except Exception as e:
                            debt_res = {
                                "status": "FAIL",
                                "error_code": "DEBT_DRAFTER_EXCEPTION",
                                "message": str(e)[:300],
                            }
                        iterations[-1]["debt_draft_status"] = str(debt_res.get("status") or "FAIL")
                        write_json(ctx.run_dir / "debt_draft_report.json", debt_res)
                        reg_debt = _load_action_register(
                            ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                        )
                        debt_action = action_from_debt_draft_result(debt_res) if isinstance(debt_res, dict) else None
                        if isinstance(debt_action, dict):
                            _upsert_actions(reg_debt, [debt_action])
                        _atomic_write_json(ctx.actions_file, reg_debt)

                        # Safe-only auto-apply (workspace incubator only).
                        if ctx.debt_policy.enabled and ctx.debt_policy.mode == "safe_apply" and auto_apply_remaining > 0:
                            chg_candidates = []
                            chg_files = debt_res.get("chg_files") if isinstance(debt_res, dict) else None
                            if isinstance(chg_files, list):
                                for item in chg_files:
                                    if isinstance(item, str) and item:
                                        chg_candidates.append(Path(item))
                            if not chg_candidates:
                                try:
                                    chg_candidates = sorted(outdir.glob("CHG-*.json"))
                                except Exception:
                                    chg_candidates = []
                            else:
                                try:
                                    for p in outdir.glob("CHG-*.json"):
                                        if p not in chg_candidates:
                                            chg_candidates.append(p)
                                except Exception:
                                    pass
                            chg_candidates = [p for p in chg_candidates if p.exists()]
                            chg_candidates.sort(key=lambda p: p.as_posix())

                            apply_action: dict[str, Any] | None = None
                            apply_result: dict[str, Any] | None = None
                            chg_target_kind: str | None = None
                            if chg_candidates:
                                chg_path = chg_candidates[0]
                                chg_obj = None
                                try:
                                    chg_obj = _load_json(chg_path)
                                except Exception:
                                    chg_obj = None
                                safe_reason = None
                                if not isinstance(chg_obj, dict):
                                    safe_reason = "CHG_INVALID"
                                else:
                                    safety = chg_obj.get("safety") if isinstance(chg_obj.get("safety"), dict) else {}
                                    if safety.get("apply_scope") != "INCUBATOR_ONLY":
                                        safe_reason = "INVALID_APPLY_SCOPE"
                                    elif safety.get("destructive") is True:
                                        safe_reason = "DESTRUCTIVE_NOT_ALLOWED"
                                    actions = chg_obj.get("actions") if isinstance(chg_obj.get("actions"), list) else []
                                    if not actions:
                                        safe_reason = "NO_ACTIONS"
                                    else:
                                        for act in actions:
                                            if not isinstance(act, dict):
                                                continue
                                            kind = act.get("kind")
                                            if not isinstance(kind, str) or kind not in ctx.debt_policy.safe_action_kinds:
                                                safe_reason = "UNSAFE_ACTION_KIND"
                                                break
                                    chg_target_kind = (
                                        chg_obj.get("target_debt_kind") if isinstance(chg_obj.get("target_debt_kind"), str) else None
                                    )

                                if safe_reason:
                                    action_id = _sha256_hex(f"DEBT_AUTO_APPLY_SKIPPED|{chg_path}|{safe_reason}")[:16]
                                    apply_action = {
                                        "action_id": action_id,
                                        "severity": "INFO",
                                        "kind": "DEBT_AUTO_APPLY_SKIPPED",
                                        "milestone_hint": "M0",
                                        "source": "DEBT_AUTOPILOT",
                                        "title": "Debt auto-apply skipped",
                                        "details": {
                                            "reason": safe_reason,
                                            "chg_path": str(chg_path),
                                        },
                                        "message": f"Auto-apply skipped: {safe_reason}",
                                        "resolved": False,
                                    }
                                    apply_result = {"status": "SKIPPED", "reason": safe_reason, "chg_path": str(chg_path)}
                                else:
                                    try:
                                        from src.ops.debt_apply_incubator import apply_debt_incubator

                                        apply_result = apply_debt_incubator(
                                            workspace_root=ctx.workspace_root,
                                            chg_path=chg_path,
                                            dry_run=False,
                                        )
                                    except Exception as e:
                                        apply_result = {
                                            "status": "FAIL",
                                            "error_code": "DEBT_AUTO_APPLY_EXCEPTION",
                                            "message": str(e)[:300],
                                        }

                                    write_json(ctx.run_dir / "debt_apply_report.json", apply_result)
                                    iterations[-1]["debt_auto_apply_status"] = str(apply_result.get("status") or "FAIL")

                                    if apply_result.get("status") == "OK":
                                        auto_apply_remaining = max(0, auto_apply_remaining - 1)
                                        debt_auto_applied = True
                                        debt_auto_applied_chg = chg_path
                                        action_id = _sha256_hex(f"DEBT_AUTO_APPLIED|{chg_path}")[:16]
                                        apply_action = {
                                            "action_id": action_id,
                                            "severity": "INFO",
                                            "kind": "DEBT_AUTO_APPLIED",
                                            "milestone_hint": "M0",
                                            "source": "DEBT_AUTOPILOT",
                                            "title": "Debt auto-apply succeeded",
                                            "details": {
                                                "chg_path": str(chg_path),
                                                "incubator_paths": apply_result.get("incubator_paths"),
                                            },
                                            "message": f"Auto-apply OK: {chg_path}",
                                            "resolved": True,
                                        }
                                    else:
                                        action_id = _sha256_hex(
                                            f"DEBT_AUTO_APPLY_FAIL|{chg_path}|{apply_result.get('status')}"
                                        )[:16]
                                        apply_action = {
                                            "action_id": action_id,
                                            "severity": "WARN",
                                            "kind": "DEBT_AUTO_APPLY_FAIL",
                                            "milestone_hint": "M0",
                                            "source": "DEBT_AUTOPILOT",
                                            "title": "Debt auto-apply failed",
                                            "details": {
                                                "chg_path": str(chg_path),
                                                "error_code": apply_result.get("error_code"),
                                            },
                                            "message": f"Auto-apply failed: {apply_result.get('error_code') or apply_result.get('status')}",
                                            "resolved": False,
                                        }
                                        if ctx.debt_policy.on_apply_fail == "block":
                                            stop_status = "BLOCKED"
                                            stop_code = "DEBT_AUTO_APPLY_FAIL"
                                            logs.append("DEBT_AUTO_APPLY_FAIL\n")

                                if apply_result is not None and not (ctx.run_dir / "debt_apply_report.json").exists():
                                    write_json(ctx.run_dir / "debt_apply_report.json", apply_result)

                                # Re-check system status after apply (optional).
                                if apply_result and apply_result.get("status") == "OK" and ctx.debt_policy.recheck_system_status:
                                    try:
                                        from src.ops.system_status_report import run_system_status

                                        system_after = run_system_status(
                                            workspace_root=ctx.workspace_root,
                                            core_root=ctx.core_root,
                                            dry_run=False,
                                        )
                                    except Exception as e:
                                        system_after = {
                                            "status": "FAIL",
                                            "error_code": "SYSTEM_STATUS_AFTER_APPLY_EXCEPTION",
                                            "message": str(e)[:300],
                                            "on_fail": "warn",
                                        }
                                    write_json(ctx.run_dir / "system_status_after_apply.json", system_after)
                                    system_after_snapshot = _system_status_snapshot_from_result(system_after)

                                    improved = False
                                    if chg_target_kind == "REPO_HYGIENE":
                                        before = _extract_repo_hygiene_count(system_status_snapshot_before)
                                        after = _extract_repo_hygiene_count(system_after_snapshot)
                                        if before is not None and after is not None and after < before:
                                            improved = True
                                    if chg_target_kind == "QUALITY_GATE_WARN":
                                        before_status = _extract_quality_status(system_status_snapshot_before)
                                        after_status = _extract_quality_status(system_after_snapshot)
                                        if after_status == "OK" and before_status in {"WARN", "FAIL"}:
                                            improved = True

                                    reg_apply = _load_action_register(
                                        ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                                    )
                                    if improved:
                                        actions_list = reg_apply.get("actions")
                                        if isinstance(actions_list, list):
                                            for a in actions_list:
                                                if not isinstance(a, dict):
                                                    continue
                                                if chg_target_kind == "REPO_HYGIENE" and (
                                                    a.get("kind") in {"REPO_HYGIENE", "REPO_HYGIENE_WARN", "REPO_HYGIENE_FAIL"}
                                                    or a.get("source") == "REPO_HYGIENE"
                                                ):
                                                    a["resolved"] = True
                                                if chg_target_kind == "QUALITY_GATE_WARN" and (
                                                    a.get("kind") == "QUALITY_GATE_WARN" or a.get("source") == "QUALITY_GATE"
                                                ):
                                                    a["resolved"] = True
                                    else:
                                        action_id = _sha256_hex(f"DEBT_NO_IMPROVEMENT|{chg_target_kind}")[:16]
                                        _upsert_actions(
                                            reg_apply,
                                            [
                                                {
                                                    "action_id": action_id,
                                                    "severity": "WARN",
                                                    "kind": "DEBT_NO_IMPROVEMENT",
                                                    "milestone_hint": "M0",
                                                    "source": "DEBT_AUTOPILOT",
                                                    "title": "Debt auto-apply did not improve status",
                                                    "details": {"target_debt_kind": chg_target_kind},
                                                    "message": "No measurable improvement after auto-apply.",
                                                    "resolved": False,
                                                }
                                            ],
                                        )
                                    _atomic_write_json(ctx.actions_file, reg_apply)

                            if apply_action is not None:
                                reg_apply = _load_action_register(
                                    ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                                )
                                _upsert_actions(reg_apply, [apply_action])
                                _atomic_write_json(ctx.actions_file, reg_apply)

                            if debt_auto_applied:
                                try:
                                    from src.ops.promotion_bundle import run_promotion_bundle

                                    promo_res = run_promotion_bundle(
                                        workspace_root=ctx.workspace_root,
                                        core_root=ctx.core_root,
                                        mode=None,
                                        dry_run=False,
                                    )
                                except Exception as e:
                                    promo_res = {
                                        "status": "FAIL",
                                        "error_code": "PROMOTION_BUNDLE_EXCEPTION",
                                        "message": str(e)[:300],
                                    }
                                promotion_status = str(promo_res.get("status") or "FAIL")
                                iterations[-1]["promotion_status"] = promotion_status

                                if isinstance(promo_res, dict):
                                    write_json(ctx.run_dir / "promotion_report_snapshot.json", promo_res)
                                    out_report = promo_res.get("out_report")
                                    if isinstance(out_report, str):
                                        report_path = Path(out_report)
                                        if report_path.exists():
                                            try:
                                                write_json(ctx.run_dir / "promotion_report_snapshot.json", _load_json(report_path))
                                            except Exception:
                                                pass
                                    out_zip = promo_res.get("out_zip")
                                    if isinstance(out_zip, str):
                                        try:
                                            write_text(ctx.run_dir / "promotion_bundle_path.txt", out_zip)
                                        except Exception:
                                            pass
                                    out_patch_md = promo_res.get("out_patch_md")
                                    if isinstance(out_patch_md, str):
                                        md_path = Path(out_patch_md)
                                        if md_path.exists():
                                            try:
                                                write_text(
                                                    ctx.run_dir / "core_patch_summary_snapshot.md",
                                                    md_path.read_text(encoding="utf-8"),
                                                )
                                            except Exception:
                                                pass

                                reg_prom = _load_action_register(
                                    ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                                )
                                if promotion_status == "OK":
                                    action_id = _sha256_hex(f"PROMOTION_BUNDLE|{promo_res.get('out_zip')}")[:16]
                                    _upsert_actions(
                                        reg_prom,
                                        [
                                            {
                                                "action_id": action_id,
                                                "severity": "INFO",
                                                "kind": "PROMOTION_BUNDLE_READY",
                                                "milestone_hint": "M0",
                                                "source": "PROMOTION_BUNDLE",
                                                "title": "Promotion bundle ready",
                                                "details": {
                                                    "included": promo_res.get("included"),
                                                    "bundle_zip": promo_res.get("out_zip"),
                                                },
                                                "message": f"Promotion bundle ready: {promo_res.get('out_zip')}",
                                                "resolved": False,
                                            }
                                        ],
                                    )
                                else:
                                    action_id = _sha256_hex(f"PROMOTION_BUNDLE_FAIL|{promo_res.get('status')}")[:16]
                                    _upsert_actions(
                                        reg_prom,
                                        [
                                            {
                                                "action_id": action_id,
                                                "severity": "WARN",
                                                "kind": "PROMOTION_BUNDLE_FAIL",
                                                "milestone_hint": "M0",
                                                "source": "PROMOTION_BUNDLE",
                                                "title": "Promotion bundle failed",
                                                "details": {
                                                    "status": promotion_status,
                                                    "error_code": promo_res.get("error_code"),
                                                },
                                                "message": f"Promotion bundle failed: {promo_res.get('error_code') or promotion_status}",
                                                "resolved": False,
                                            }
                                        ],
                                    )
                                _atomic_write_json(ctx.actions_file, reg_prom)

            if not ctx.smoke_drift_minimal:
                completed_set = set(
                    str(x) for x in (roadmap_state.get("completed_milestones") or []) if isinstance(x, str)
                )
                if "M8.2" not in completed_set:
                    seed_path = ctx.workspace_root / "incubator" / "notes" / "PROMOTION_SEED.md"
                    seed_exists = seed_path.exists()
                    should_attempt = debt_auto_applied or seed_exists
                    if _promotion_outputs_exist(ctx.workspace_root):
                        mark_completed(roadmap_state, "M8.2")
                        save_state(state_path=ctx.state_path, state=roadmap_state)
                        completed_set.add("M8.2")
                    elif should_attempt:
                        if not _incubator_has_files(ctx.workspace_root):
                            try:
                                _ensure_promotion_seed_note(ctx.workspace_root)
                            except ValueError:
                                stop_status = "BLOCKED"
                                stop_code = "PROMOTION_SEED_CONTENT_MISMATCH"
                                logs.append("PROMOTION_SEED_CONTENT_MISMATCH\n")
                                break

                        try:
                            from src.roadmap.executor import apply_roadmap

                            m82_res = apply_roadmap(
                                roadmap_path=ctx.roadmap_path,
                                core_root=ctx.core_root,
                                workspace_root=ctx.workspace_root,
                                cache_root=ctx.core_root / ".cache",
                                evidence_root=ctx.core_root / "evidence" / "roadmap",
                                dry_run=False,
                                dry_run_mode="simulate",
                                milestone_ids=["M8.2"],
                            )
                        except Exception as e:
                            m82_res = {
                                "status": "FAIL",
                                "error_code": "M8_2_APPLY_EXCEPTION",
                                "message": str(e)[:300],
                            }
                        write_json(ctx.run_dir / "promotion_bundle_apply_report.json", m82_res)

                        if m82_res.get("status") == "OK" and _promotion_outputs_exist(ctx.workspace_root):
                            mark_completed(roadmap_state, "M8.2")
                            save_state(state_path=ctx.state_path, state=roadmap_state)
                            completed_set.add("M8.2")

                            report_path = ctx.workspace_root / ".cache" / "promotion" / "promotion_report.v1.json"
                            if report_path.exists():
                                try:
                                    write_json(ctx.run_dir / "promotion_report_snapshot.json", _load_json(report_path))
                                except Exception:
                                    pass
                            patch_md = ctx.workspace_root / ".cache" / "promotion" / "core_patch_summary.v1.md"
                            if patch_md.exists():
                                try:
                                    write_text(
                                        ctx.run_dir / "core_patch_summary_snapshot.md",
                                        patch_md.read_text(encoding="utf-8"),
                                    )
                                except Exception:
                                    pass
                            zip_path = ctx.workspace_root / ".cache" / "promotion" / "promotion_bundle.v1.zip"
                            if zip_path.exists():
                                try:
                                    write_text(ctx.run_dir / "promotion_bundle_path.txt", str(zip_path))
                                except Exception:
                                    pass

                            included = 0
                            if report_path.exists():
                                try:
                                    obj = _load_json(report_path)
                                    inc = obj.get("included_files") if isinstance(obj, dict) else None
                                    included = len(inc) if isinstance(inc, list) else 0
                                except Exception:
                                    included = 0

                            reg_prom = _load_action_register(
                                ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                            )
                            action_id = _sha256_hex(f"PROMOTION_BUNDLE|{zip_path.as_posix()}")[:16]
                            _upsert_actions(
                                reg_prom,
                                [
                                    {
                                        "action_id": action_id,
                                        "severity": "INFO",
                                        "kind": "PROMOTION_BUNDLE_READY",
                                        "milestone_hint": "M8.2",
                                        "source": "PROMOTION_BUNDLE",
                                        "title": "Promotion bundle ready",
                                        "details": {"included": included, "bundle_zip": str(zip_path)},
                                        "message": f"Promotion bundle ready: {zip_path}",
                                        "resolved": False,
                                    }
                                ],
                            )
                            _atomic_write_json(ctx.actions_file, reg_prom)
                        elif m82_res.get("status") != "OK":
                            reg_prom = _load_action_register(
                                ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root
                            )
                            action_id = _sha256_hex("PROMOTION_BUNDLE_FAIL|M8.2")[:16]
                            _upsert_actions(
                                reg_prom,
                                [
                                    {
                                        "action_id": action_id,
                                        "severity": "WARN",
                                        "kind": "PROMOTION_BUNDLE_FAIL",
                                        "milestone_hint": "M8.2",
                                        "source": "PROMOTION_BUNDLE",
                                        "title": "Promotion bundle failed",
                                        "details": {
                                            "status": m82_res.get("status"),
                                            "error_code": m82_res.get("error_code"),
                                        },
                                        "message": f"Promotion bundle failed: {m82_res.get('error_code') or m82_res.get('status')}",
                                        "resolved": False,
                                    }
                                ],
                            )
                            _atomic_write_json(ctx.actions_file, reg_prom)

            if ctx.core_policy.enabled:
                ok, code = _enforce_core_clean(phase=f"iteration:{milestone_id}")
                if not ok:
                    stop_status = "BLOCKED"
                    stop_code = code or "CORE_WRITE_VIOLATION"
                    break

            st_after = load_state(
                state_path=ctx.state_path,
                schema_path=ctx.state_schema,
                roadmap_path=ctx.roadmap_path,
                workspace_root=ctx.workspace_root,
            ).state
            record_last_result(
                st_after,
                status="OK" if res.get("status") in {"OK", "DONE"} else "FAIL",
                milestone_id=milestone_id,
                evidence_path=(
                    res.get("evidence")[-1]
                    if isinstance(res.get("evidence"), list) and res.get("evidence")
                    else None
                ),
                error_code=str(res.get("error_code") or "")[:200] if res.get("error_code") else None,
            )
            save_state(state_path=ctx.state_path, state=st_after)

            if res.get("status") == "DONE":
                stop_status = "DONE"
                break
            if res.get("status") == "OK":
                continue
            if res.get("status") == "BLOCKED" and res.get("error_code") == "BACKOFF":
                # Bounded sleep; allow sleep_seconds=0 for deterministic smoke runs.
                if ctx.sleep_seconds <= 0:
                    stop_status = "BLOCKED"
                    stop_code = "BACKOFF"
                    break
                next_try_at = None
                b = st_after.get("backoff") if isinstance(st_after.get("backoff"), dict) else {}
                if isinstance(b, dict) and isinstance(b.get("next_try_at"), str):
                    next_try_at = _parse_iso8601(b.get("next_try_at"))
                if next_try_at is not None:
                    remaining = max(0, int((next_try_at - _now_utc()).total_seconds()))
                    time.sleep(min(int(ctx.sleep_seconds), remaining))
                else:
                    time.sleep(int(ctx.sleep_seconds))
                slept_for_backoff = True
                break

            stop_status = str(res.get("status") or "BLOCKED")
            stop_code = str(res.get("error_code") or "FAILED")
            break

        if stop_status is not None:
            break
        if slept_for_backoff:
            continue
        # Completed a batch; continue until DONE/BLOCKED or time limit.
        continue

    # Final payload
    state_after = load_state(
        state_path=ctx.state_path,
        schema_path=ctx.state_schema,
        roadmap_path=ctx.roadmap_path,
        workspace_root=ctx.workspace_root,
    ).state
    completed_after = state_after.get("completed_milestones", [])
    next_after = _next_milestone(ctx.roadmap_ids, completed_after if isinstance(completed_after, list) else [])
    if stop_status is None:
        out_status = "DONE" if next_after is None else "OK"
    else:
        out_status = stop_status
    error_code = stop_code
    if error_code is None:
        last_result = state_after.get("last_result") if isinstance(state_after.get("last_result"), dict) else {}
        error_code = last_result.get("error_code") if isinstance(last_result, dict) else None
    if out_status == "OK" and next_after is None:
        out_status = "DONE"

    action_from_system_status_result = None
    try:
        from src.ops.system_status_report import action_from_system_status_result as _action_from_system_status_result
        from src.ops.system_status_report import run_system_status

        action_from_system_status_result = _action_from_system_status_result
        system_final = run_system_status(workspace_root=ctx.workspace_root, core_root=ctx.core_root, dry_run=False)
    except Exception as e:
        system_final = {
            "status": "FAIL",
            "error_code": "SYSTEM_STATUS_FINAL_EXCEPTION",
            "message": str(e)[:300],
            "on_fail": "warn",
        }
    system_status_status = str(system_final.get("status") or "FAIL")
    write_json(ctx.run_dir / "system_status_report.json", system_final)
    out_json = system_final.get("out_json") if isinstance(system_final, dict) else None
    if isinstance(out_json, str) and out_json:
        json_path = Path(out_json)
        if json_path.exists():
            try:
                write_json(ctx.run_dir / "system_status_snapshot.json", _load_json(json_path))
            except Exception:
                pass
    out_md = system_final.get("out_md") if isinstance(system_final, dict) else None
    if isinstance(out_md, str) and out_md:
        md_path = Path(out_md)
        if md_path.exists():
            try:
                write_text(ctx.run_dir / "system_status_snapshot.md", md_path.read_text(encoding="utf-8"))
            except Exception:
                pass
    reg_sys_final = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
    sys_action = (
        action_from_system_status_result(system_final)
        if callable(action_from_system_status_result) and isinstance(system_final, dict)
        else None
    )
    if isinstance(sys_action, dict):
        _upsert_actions(reg_sys_final, [sys_action])
    _atomic_write_json(ctx.actions_file, reg_sys_final)

    if ctx.core_policy.enabled:
        ok, code = _enforce_core_clean(phase="final")
        if not ok:
            out_status = "BLOCKED"
            error_code = code or "CORE_WRITE_VIOLATION"

    actions_after = _load_action_register(ctx.actions_file, roadmap_path=ctx.roadmap_path, workspace_root=ctx.workspace_root)
    _atomic_write_json(ctx.run_dir / "actions_after.json", actions_after)

    actions_list = actions_after.get("actions") if isinstance(actions_after, dict) else None
    unresolved_actions = (
        [a for a in actions_list if isinstance(a, dict) and a.get("resolved") is not True]
        if isinstance(actions_list, list)
        else []
    )
    unresolved_actions.sort(key=lambda x: str(x.get("action_id") or ""))
    actions_count = len(unresolved_actions)
    top_actions = []
    for a in unresolved_actions[:5]:
        top_actions.append(
            {
                "action_id": a.get("action_id"),
                "severity": a.get("severity"),
                "kind": a.get("kind"),
                "milestone_hint": a.get("milestone_hint") or a.get("target_milestone"),
                "title": a.get("title"),
                "message": a.get("message"),
            }
        )

    # Session RAM (Ephemeral SSOT) hook (v0.1): if default session exists, capture its hash in evidence output.
    session_context_hash: str | None = None
    try:
        sp = SessionPaths(workspace_root=ctx.workspace_root, session_id="default")
        if sp.context_path.exists():
            ctx_obj = load_context(sp.context_path)
            hashes = ctx_obj.get("hashes") if isinstance(ctx_obj, dict) else None
            sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
            if isinstance(sha, str) and len(sha) == 64:
                session_context_hash = sha
    except SessionContextError:
        session_context_hash = None
    except Exception:
        session_context_hash = None

    # v0.4: If the roadmap is fully DONE but debt remains in the Action Register, surface it explicitly.
    if out_status == "DONE" and actions_count > 0:
        out_status = "DONE_WITH_DEBT"

    core_unlock_requested = _core_unlock_requested(ctx.core_policy)
    core_unlock_allowed = core_unlock_requested and ctx.core_policy.default_mode == "locked"

    out = {
        "status": out_status,
        "next_milestone": next_after,
        "completed": completed_after if isinstance(completed_after, list) else [],
        "iterations": len(iterations),
        "chg_generated": chg_generated,
        "error_code": error_code,
        "script_budget_status": script_budget_status,
        "quality_gate_status": quality_gate_status,
        "harvest_status": harvest_status,
        "ops_index_status": ops_index_status,
        "advisor_status": advisor_status,
        "autopilot_readiness_status": autopilot_readiness_status,
        "system_status_status": system_status_status,
        "artifact_completeness": {
            "missing_count": len(ctx.artifact_completeness.get("missing", []))
            if isinstance(ctx.artifact_completeness, dict)
            else 0,
            "healed_count": len(ctx.artifact_completeness.get("healed", []))
            if isinstance(ctx.artifact_completeness, dict)
            else 0,
            "still_missing_count": len(ctx.artifact_completeness.get("still_missing", []))
            if isinstance(ctx.artifact_completeness, dict)
            else 0,
        },
        "smoke_drift_minimal": ctx.smoke_drift_minimal,
        "skipped_ingest": ctx.skipped_ingest,
        "session_context_hash": session_context_hash,
        "roadmap_sha256": ctx.drift_info.get("roadmap_sha256"),
        "drift_detected": ctx.drift_info.get("drift_detected"),
        "stale_milestones": ctx.drift_info.get("stale_milestones"),
        "stale_reset_milestones": ctx.drift_info.get("stale_reset_milestones"),
        "actions_count": actions_count,
        "top_actions": top_actions,
        "pack_conflict_blocked": ctx.pack_conflict_blocked,
        "pack_conflict_report_path": ctx.pack_conflict_report_path,
        "core_lock_enabled": bool(ctx.core_policy.enabled),
        "core_lock_mode": ctx.core_policy.default_mode,
        "core_unlock_env_var": ctx.core_policy.allow_env_var,
        "core_unlock_requested": core_unlock_requested,
        "core_unlock_allowed": core_unlock_allowed,
    }

    state.script_budget_status = script_budget_status
    state.quality_gate_status = quality_gate_status
    state.harvest_status = harvest_status
    state.ops_index_status = ops_index_status
    state.advisor_status = advisor_status
    state.autopilot_readiness_status = autopilot_readiness_status
    state.system_status_status = system_status_status
    state.system_status_snapshot_before = system_status_snapshot_before
    state.promotion_status = promotion_status
    state.debt_auto_applied = debt_auto_applied
    state.auto_apply_remaining = auto_apply_remaining
    state.stop_status = stop_status
    state.stop_code = stop_code

    return FinishLoopResult(
        out=out,
        iterations=iterations,
        logs=logs,
        state_after=state_after,
        actions_after=actions_after,
    )
