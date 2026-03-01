from __future__ import annotations

import json
import time

from src.evidence.writer import EvidenceWriter
from src.orchestrator import autonomy, budget_runtime, dlq, quota
from src.orchestrator.executor_adapters import resolve_executor_port
from src.orchestrator.observability.otel_bridge import attach_trace_meta
from src.orchestrator.runner_stages.context import ExecutionContext, StageContext
from src.tools.gateway import PolicyViolation


def execute_and_finalize_stage(*, stage_ctx: StageContext, exec_ctx: ExecutionContext) -> None:
    run_ctx = exec_ctx.run_ctx
    routing_state = exec_ctx.routing_state
    idempotency_state = exec_ctx.idempotency_state
    quota_autonomy_state = exec_ctx.quota_autonomy_state

    evidence = EvidenceWriter(out_dir=stage_ctx.out_dir, run_id=exec_ctx.run_id)
    evidence.write_request(stage_ctx.envelope)

    executor = resolve_executor_port(workspace=stage_ctx.workspace)
    provider_used_default = "stub"
    model_used_default = None

    try:
        exec_started_at = dlq.iso_utc_now()
        exec_t0 = time.perf_counter()
        exec_summary = executor.execute_workflow(
            envelope=stage_ctx.envelope,
            workflow=routing_state.workflow,
            workspace=stage_ctx.workspace,
            evidence=evidence,
            approval_threshold=routing_state.approval_threshold_used,
            writes_allowed=run_ctx.writes_allowed,
            budget=routing_state.budget,
            force_suspend_reason=quota_autonomy_state.autonomy_gate_triggered,
        )
        finished_at = dlq.iso_utc_now()
        duration_ms = int((time.perf_counter() - exec_t0) * 1000)
        budget_usage = budget_runtime.budget_usage_dict(routing_state.budget, fallback_elapsed_ms=duration_ms)

        if quota_autonomy_state.quota_store_updated:
            est_tokens_after = int(quota_autonomy_state.est_tokens_used_before) + int(
                budget_usage.get("est_tokens_used", 0)
            )
            quota.set_quota_usage(
                quota_autonomy_state.quota_store,
                date_key=quota_autonomy_state.quota_date,
                tenant_id=run_ctx.tenant_id,
                runs_used=int(quota_autonomy_state.runs_used_before) + 1,
                est_tokens_used=est_tokens_after,
            )
            quota.save_quota_store(quota_autonomy_state.quota_store_path, quota_autonomy_state.quota_store)
            quota_autonomy_state.quota_usage_after = {
                "runs_used": int(quota_autonomy_state.runs_used_before) + 1,
                "est_tokens_used": est_tokens_after,
            }

        provider_used = exec_summary.get("provider_used") or provider_used_default
        model_used = (
            exec_summary.get("model_used") if exec_summary.get("model_used") is not None else model_used_default
        )
        secrets_used = exec_summary.get("secrets_used", [])
        secrets_used_list = secrets_used if isinstance(secrets_used, list) else []

        summary = {
            "run_id": exec_ctx.run_id,
            "request_id": run_ctx.request_id,
            "tenant_id": run_ctx.tenant_id,
            "workflow_id": run_ctx.workflow_id,
            "result_state": exec_summary.get("status"),
            "status": exec_summary.get("status"),
            "approval_threshold_used": routing_state.approval_threshold_used,
            "threshold_used": routing_state.approval_threshold_used,
            "risk_score": run_ctx.risk_score,
            "intent": run_ctx.intent,
            "workflow_path": str(routing_state.workflow_path),
            "dry_run": run_ctx.dry_run,
            "provider_used": provider_used,
            "model_used": model_used,
            "secrets_used": secrets_used_list,
            "workflow_fingerprint": routing_state.workflow_fingerprint,
            "started_at": exec_started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": idempotency_state.idempotency_key_hash,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "budget": budget_runtime.budget_spec_dict(routing_state.budget_spec),
            "budget_usage": budget_usage,
            "budget_hit": None,
            "quota": quota_autonomy_state.quota_spec,
            "quota_usage_before": quota_autonomy_state.quota_usage_before,
            "quota_usage_after": quota_autonomy_state.quota_usage_after,
            "quota_hit": None,
            "governor_mode_used": run_ctx.governor_mode_used,
            "governor_quarantine_hit": run_ctx.governor_quarantine_hit,
            "governor_concurrency_limit_hit": run_ctx.governor_concurrency_limit_hit,
            "nodes": exec_summary.get("nodes", []),
        }
        if "token_usage" in exec_summary:
            summary["token_usage"] = exec_summary.get("token_usage")
    except Exception as e:
        provider_used_on_error = getattr(e, "provider_used", provider_used_default)
        model_used_on_error = getattr(e, "model_used", model_used_default)
        secrets_used_on_error = getattr(e, "secrets_used", [])
        secrets_used_list = secrets_used_on_error if isinstance(secrets_used_on_error, list) else []

        if isinstance(e, PolicyViolation):
            msg = f"{e.error_code}: {e}"
            if len(msg) > 240:
                msg = msg[:237] + "..."
            if budget_runtime.is_budget_policy_violation(e.error_code):
                stage = "BUDGET"
            elif quota.is_quota_policy_violation(e.error_code):
                stage = "QUOTA"
            else:
                stage = "EXECUTION"
            dlq.write_dlq_record(
                workspace=stage_ctx.workspace,
                stage=stage,
                error_code="POLICY_VIOLATION",
                message=msg or "Policy violation during execution.",
                envelope=stage_ctx.envelope,
                workflow_id=run_ctx.workflow_id,
            )
        finished_at = dlq.iso_utc_now()
        duration_ms = int((time.perf_counter() - routing_state.t0) * 1000)
        budget_usage = budget_runtime.budget_usage_dict(routing_state.budget, fallback_elapsed_ms=duration_ms)
        quota_hit = quota.quota_hit_from_policy_violation(e.error_code) if isinstance(e, PolicyViolation) else None

        if quota_autonomy_state.quota_store_updated:
            est_tokens_after = int(quota_autonomy_state.est_tokens_used_before) + int(
                budget_usage.get("est_tokens_used", 0)
            )
            quota.set_quota_usage(
                quota_autonomy_state.quota_store,
                date_key=quota_autonomy_state.quota_date,
                tenant_id=run_ctx.tenant_id,
                runs_used=int(quota_autonomy_state.runs_used_before) + 1,
                est_tokens_used=est_tokens_after,
            )
            quota.save_quota_store(quota_autonomy_state.quota_store_path, quota_autonomy_state.quota_store)
            quota_autonomy_state.quota_usage_after = {
                "runs_used": int(quota_autonomy_state.runs_used_before) + 1,
                "est_tokens_used": est_tokens_after,
            }
        summary = {
            "run_id": exec_ctx.run_id,
            "request_id": run_ctx.request_id,
            "tenant_id": run_ctx.tenant_id,
            "workflow_id": run_ctx.workflow_id,
            "result_state": "FAILED",
            "status": "FAILED",
            "approval_threshold_used": routing_state.approval_threshold_used,
            "threshold_used": routing_state.approval_threshold_used,
            "risk_score": run_ctx.risk_score,
            "intent": run_ctx.intent,
            "workflow_path": str(routing_state.workflow_path),
            "dry_run": run_ctx.dry_run,
            "provider_used": provider_used_on_error,
            "model_used": model_used_on_error,
            "secrets_used": secrets_used_list,
            "workflow_fingerprint": routing_state.workflow_fingerprint,
            "started_at": routing_state.started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": idempotency_state.idempotency_key_hash,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "budget": budget_runtime.budget_spec_dict(routing_state.budget_spec),
            "budget_usage": budget_usage,
            "budget_hit": budget_runtime.budget_hit_from_policy_violation(e.error_code)
            if isinstance(e, PolicyViolation)
            else None,
            "quota": quota_autonomy_state.quota_spec,
            "quota_usage_before": quota_autonomy_state.quota_usage_before,
            "quota_usage_after": quota_autonomy_state.quota_usage_after,
            "quota_hit": quota_hit,
            "governor_mode_used": run_ctx.governor_mode_used,
            "governor_quarantine_hit": run_ctx.governor_quarantine_hit,
            "governor_concurrency_limit_hit": run_ctx.governor_concurrency_limit_hit,
            "error_code": "POLICY_VIOLATION" if isinstance(e, PolicyViolation) else None,
            "policy_violation_code": e.error_code if isinstance(e, PolicyViolation) else None,
            "error": str(e),
        }

    if stage_ctx.replay_of is not None:
        summary["replay_of"] = stage_ctx.replay_of
        summary["replay_warnings"] = list(stage_ctx.replay_warnings)

    # Progressive autonomy (v0.1): add evidence fields and update store on terminal outcomes.
    summary["autonomy_mode_used"] = quota_autonomy_state.autonomy_mode_used
    summary["autonomy_gate_triggered"] = quota_autonomy_state.autonomy_gate_triggered

    autonomy_outcome: str | None = None
    result_state = summary.get("result_state")
    if result_state == "COMPLETED" and summary.get("policy_violation_code") is None and summary.get("error_code") is None:
        autonomy_outcome = "SUCCESS"
    elif result_state == "FAILED":
        autonomy_outcome = "FAIL"

    if autonomy_outcome is not None:
        quota_autonomy_state.autonomy_record = autonomy.update_autonomy_record(
            quota_autonomy_state.autonomy_record,
            outcome=autonomy_outcome,
            cfg_mode=str(quota_autonomy_state.autonomy_cfg.get("mode", "human_review")),
            success_threshold=float(quota_autonomy_state.autonomy_cfg.get("success_threshold", 0.8)),
            min_samples=int(quota_autonomy_state.autonomy_cfg.get("min_samples", 5)),
        )
        quota_autonomy_state.autonomy_store[run_ctx.intent] = quota_autonomy_state.autonomy_record
        autonomy.save_autonomy_store(quota_autonomy_state.autonomy_store_path, quota_autonomy_state.autonomy_store)

    summary["autonomy_store_snapshot"] = {
        "samples": int(quota_autonomy_state.autonomy_record.get("samples", 0)),
        "successes": int(quota_autonomy_state.autonomy_record.get("successes", 0)),
        "mode": quota_autonomy_state.autonomy_record.get("mode"),
    }

    attach_trace_meta(summary, workspace=stage_ctx.workspace, out_dir=stage_ctx.out_dir, run_id=exec_ctx.run_id)
    evidence.write_summary(summary)
    if summary.get("result_state") == "SUSPENDED":
        resume_path = evidence.run_dir
        try:
            resume_path = evidence.run_dir.resolve().relative_to(stage_ctx.workspace.resolve())
        except ValueError:
            resume_path = evidence.run_dir

        suspend_reason = "APPROVAL_REQUIRED"
        if summary.get("autonomy_gate_triggered") in {"AUTONOMY_MANUAL_ONLY", "AUTONOMY_HUMAN_REVIEW"}:
            suspend_reason = str(summary.get("autonomy_gate_triggered"))
        evidence.write_suspend(
            {
                "run_id": exec_ctx.run_id,
                "reason": suspend_reason,
                "risk_score": run_ctx.risk_score,
                "threshold_used": routing_state.approval_threshold_used,
                "next_action_hint": f"Resume with --resume {resume_path} --approve true",
            }
        )
    evidence.write_provenance(workspace=stage_ctx.workspace, summary=summary)
    evidence.write_integrity_manifest()
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if summary.get("status") == "FAILED":
        raise SystemExit(1)
