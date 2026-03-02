from __future__ import annotations

from dataclasses import dataclass
import json
import time
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator import autonomy, budget_runtime, dlq, quota, runner_config
from src.orchestrator.observability.otel_bridge import attach_trace_meta
from src.orchestrator.runner_context import RunContext
from src.orchestrator.runner_stages.context import StageContext
from src.orchestrator.runner_stages.idempotency_stage import IdempotencyState
from src.orchestrator.runner_stages.routing_workflow_stage import RoutingWorkflowState


@dataclass
class QuotaAutonomyState:
    quota_store_path: Path
    quota_store: dict[str, Any]
    quota_date: str
    runs_used_before: int
    est_tokens_used_before: int
    quota_spec: dict[str, Any]
    quota_usage_before: dict[str, Any]
    quota_usage_after: dict[str, Any]
    quota_store_updated: bool
    autonomy_store_path: Path
    autonomy_store: dict[str, Any]
    autonomy_cfg: dict[str, Any]
    autonomy_record: dict[str, Any]
    autonomy_mode_used: str
    autonomy_gate_triggered: str | None


def quota_autonomy_stage(
    *,
    stage_ctx: StageContext,
    run_ctx: RunContext,
    run_id: str,
    routing_state: RoutingWorkflowState,
    idempotency_state: IdempotencyState,
) -> QuotaAutonomyState:
    quota_policy = runner_config.load_quota_policy(stage_ctx.workspace)
    quota_store_path = stage_ctx.workspace / ".cache" / "tenant_quota_store.v1.json"
    quota_date = quota.utc_date_key()
    quota_store = quota.load_quota_store(quota_store_path)
    runs_used_before, est_tokens_used_before = quota.get_quota_usage(
        quota_store, date_key=quota_date, tenant_id=run_ctx.tenant_id
    )
    max_runs_per_day, max_est_tokens_per_day = quota.quota_limits_for_tenant(quota_policy, run_ctx.tenant_id)
    quota_spec = {"max_runs_per_day": max_runs_per_day, "max_est_tokens_per_day": max_est_tokens_per_day}
    quota_usage_before = {"runs_used": runs_used_before, "est_tokens_used": est_tokens_used_before}
    quota_usage_after = dict(quota_usage_before)
    quota_store_updated = False

    autonomy_policy = runner_config.load_autonomy_policy(stage_ctx.workspace)
    autonomy_cfg = autonomy.autonomy_cfg_for_intent(autonomy_policy, run_ctx.intent)
    autonomy_store_path = stage_ctx.workspace / ".cache" / "autonomy_store.v1.json"
    autonomy_store = autonomy.load_autonomy_store(autonomy_store_path)
    autonomy_record = autonomy.autonomy_record_for_intent(
        autonomy_store, run_ctx.intent, initial_mode=str(autonomy_cfg.get("mode", "human_review"))
    )
    autonomy_mode_used = autonomy_record.get("mode", "human_review")

    side_effect_policy = stage_ctx.envelope.get("side_effect_policy", "none")
    side_effect_policy = side_effect_policy if isinstance(side_effect_policy, str) else "none"

    autonomy_gate_triggered = autonomy.autonomy_gate_triggered(
        autonomy_mode_used=str(autonomy_mode_used),
        dry_run=bool(run_ctx.dry_run),
        side_effect_policy=str(side_effect_policy),
    )

    if int(runs_used_before) + 1 > int(max_runs_per_day):
        msg = (
            "QUOTA_RUNS_EXCEEDED: "
            f"runs_used {int(runs_used_before)} + 1 > max_runs_per_day {int(max_runs_per_day)}"
        )
        dlq_path = dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="QUOTA",
            error_code="POLICY_VIOLATION",
            message=msg,
            envelope=stage_ctx.envelope,
            workflow_id=run_ctx.workflow_id,
        )

        evidence = EvidenceWriter(out_dir=stage_ctx.out_dir, run_id=run_id)
        evidence.write_request(stage_ctx.envelope)

        finished_at = dlq.iso_utc_now()
        duration_ms = int((time.perf_counter() - routing_state.t0) * 1000)
        budget_usage = budget_runtime.budget_usage_dict(routing_state.budget, fallback_elapsed_ms=duration_ms)

        updated_record = autonomy.update_autonomy_record(
            autonomy_record,
            outcome="FAIL",
            cfg_mode=str(autonomy_cfg.get("mode", "human_review")),
            success_threshold=float(autonomy_cfg.get("success_threshold", 0.8)),
            min_samples=int(autonomy_cfg.get("min_samples", 5)),
        )
        autonomy_store[run_ctx.intent] = updated_record
        autonomy.save_autonomy_store(autonomy_store_path, autonomy_store)
        autonomy_snapshot = {
            "samples": int(updated_record.get("samples", 0)),
            "successes": int(updated_record.get("successes", 0)),
            "mode": updated_record.get("mode"),
        }
        summary = {
            "run_id": run_id,
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
            "provider_used": "stub",
            "model_used": None,
            "secrets_used": [],
            "workflow_fingerprint": routing_state.workflow_fingerprint,
            "started_at": routing_state.started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": idempotency_state.idempotency_key_hash,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "budget": budget_runtime.budget_spec_dict(routing_state.budget_spec),
            "budget_usage": budget_usage,
            "budget_hit": None,
            "quota": quota_spec,
            "quota_usage_before": quota_usage_before,
            "quota_usage_after": quota_usage_after,
            "quota_hit": "RUNS",
            "autonomy_mode_used": autonomy_mode_used,
            "autonomy_store_snapshot": autonomy_snapshot,
            "autonomy_gate_triggered": autonomy_gate_triggered,
            "governor_mode_used": run_ctx.governor_mode_used,
            "governor_quarantine_hit": run_ctx.governor_quarantine_hit,
            "governor_concurrency_limit_hit": run_ctx.governor_concurrency_limit_hit,
            "error_code": "POLICY_VIOLATION",
            "policy_violation_code": "QUOTA_RUNS_EXCEEDED",
            "error": msg,
            "dlq_file": dlq_path.name,
        }
        if stage_ctx.replay_of is not None:
            summary["replay_of"] = stage_ctx.replay_of
            summary["replay_warnings"] = list(stage_ctx.replay_warnings)
        attach_trace_meta(summary, workspace=stage_ctx.workspace, out_dir=stage_ctx.out_dir, run_id=run_id)
        evidence.write_summary(summary)
        evidence.write_provenance(workspace=stage_ctx.workspace, summary=summary)
        evidence.write_integrity_manifest()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    quota.set_quota_usage(
        quota_store,
        date_key=quota_date,
        tenant_id=run_ctx.tenant_id,
        runs_used=int(runs_used_before) + 1,
        est_tokens_used=int(est_tokens_used_before),
    )
    quota.save_quota_store(quota_store_path, quota_store)
    quota_store_updated = True

    # Enforce token quota during execution (fail before side effects).
    routing_state.budget.set_quota_context(
        max_est_tokens_per_day=max_est_tokens_per_day,
        est_tokens_used_before=est_tokens_used_before,
    )

    return QuotaAutonomyState(
        quota_store_path=quota_store_path,
        quota_store=quota_store,
        quota_date=quota_date,
        runs_used_before=runs_used_before,
        est_tokens_used_before=est_tokens_used_before,
        quota_spec=quota_spec,
        quota_usage_before=quota_usage_before,
        quota_usage_after=quota_usage_after,
        quota_store_updated=quota_store_updated,
        autonomy_store_path=autonomy_store_path,
        autonomy_store=autonomy_store,
        autonomy_cfg=autonomy_cfg,
        autonomy_record=autonomy_record,
        autonomy_mode_used=autonomy_mode_used,
        autonomy_gate_triggered=autonomy_gate_triggered,
    )
