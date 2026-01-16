from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.ops.commands.extension_cmds import (
    cmd_deploy_job_start,
    cmd_github_ops_job_start,
    cmd_release_check,
)
from src.ops.commands.maintenance_cmds import (
    cmd_work_intake_check,
    cmd_work_intake_exec_ticket,
)
from src.prj_airunner.airunner_tick_utils import _run_cmd_json_with_perf
from src.prj_airunner.airunner_tick_support_v2 import seed_network_live_decision
from src.prj_airunner.auto_mode_dispatch import (
    auto_mode_network_allowed,
    network_live_gate_status,
    write_plan_only,
    write_selection_file,
)


def run_auto_mode_actions(
    *,
    workspace_root: Path,
    dispatch_plan: dict[str, Any],
    auto_mode_policy: dict[str, Any],
    allowed_ops: list[str],
    can_start_github: bool,
    can_start_deploy: bool,
    max_dispatch_jobs: int,
    max_dispatch_actions: int,
    perf_cfg: dict[str, Any],
    work_intake_path: str | None,
    evidence_paths: list[str],
    ops_called: list[str],
    notes: list[str],
) -> dict[str, Any]:
    dispatched_extensions = list(dispatch_plan.get("dispatched_extensions") or [])
    selected_ids = list(dispatch_plan.get("selected_ids") or [])
    dispatch_jobs_started = 0
    dispatch_idle_reason = ""
    dispatch_plan_path = ""
    exec_payload: dict[str, Any] | None = None
    exec_path = ""

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
        work_intake_path = (
            work_intake_payload.get("work_intake_path") if isinstance(work_intake_payload, dict) else work_intake_path
        )
        if isinstance(work_intake_path, str) and work_intake_path:
            evidence_paths.append(work_intake_path)

    job_candidates = dispatch_plan.get("job_candidates") if isinstance(dispatch_plan.get("job_candidates"), list) else []
    for job in job_candidates[: max(0, int(max_dispatch_jobs))]:
        extension_id = str(job.get("extension_id") or "")
        job_kind = str(job.get("job_kind") or "")
        live_allowed, live_reason = network_live_gate_status(workspace_root=workspace_root)
        if not live_allowed:
            dispatch_idle_reason = "BLOCKED_BY_DECISION"
            notes.append(f"network_live_gate={live_reason}")
            seed_network_live_decision(
                workspace_root=workspace_root,
                evidence_paths=evidence_paths,
                ops_called=ops_called,
                notes=notes,
                reason=live_reason,
            )
            break
        allow_network, net_reason = auto_mode_network_allowed(
            workspace_root=workspace_root, policy=auto_mode_policy, extension_id=extension_id
        )
        if extension_id == "PRJ-GITHUB-OPS":
            if not can_start_github:
                dispatch_idle_reason = "OP_NOT_ALLOWED"
                break
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
        elif extension_id == "PRJ-DEPLOY":
            if not can_start_deploy:
                dispatch_idle_reason = "OP_NOT_ALLOWED"
                break
            mode = "live" if allow_network else "dry_run_only"
            payload_ref = str(job.get("intake_id") or str(Path(".cache") / "reports" / "deploy_plan.v1.json"))
            start_payload = _run_cmd_json_with_perf(
                op_name="deploy-job-start",
                func=cmd_deploy_job_start,
                args=argparse.Namespace(
                    workspace_root=str(workspace_root),
                    kind=job_kind,
                    payload=payload_ref,
                    mode=mode,
                ),
                workspace_root=workspace_root,
                perf_cfg=perf_cfg,
            )
            ops_called.append("deploy-job-start")
        else:
            dispatch_idle_reason = "EXTENSION_UNSUPPORTED"
            break
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

    plan_candidates = dispatch_plan.get("plan_candidates") if isinstance(dispatch_plan.get("plan_candidates"), list) else []
    dispatch_plan_path = write_plan_only(
        workspace_root=workspace_root,
        plan_candidates=plan_candidates,
        reason="AUTO_MODE_PLAN_ONLY",
    )
    if dispatch_plan_path:
        evidence_paths.append(dispatch_plan_path)

    return {
        "dispatch_plan_path": dispatch_plan_path,
        "dispatched_extensions": dispatched_extensions,
        "dispatch_jobs_started": dispatch_jobs_started,
        "dispatch_idle_reason": dispatch_idle_reason,
        "exec_payload": exec_payload,
        "exec_path": exec_path,
        "work_intake_path": work_intake_path,
    }
