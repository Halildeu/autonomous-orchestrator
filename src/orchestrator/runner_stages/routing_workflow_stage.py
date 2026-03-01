from __future__ import annotations

from dataclasses import dataclass
import json
import time
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator import budget_runtime, dlq, idempotency, validation
from src.orchestrator.observability.otel_bridge import attach_trace_meta
from src.orchestrator.route import load_strategy_table, route_intent
from src.orchestrator.runner_context import RunContext
from src.orchestrator.runner_stages.context import StageContext
from src.orchestrator.runner_utils import hash_json_dir, print_error
from src.orchestrator.workflow_exec import BudgetTracker, read_approval_threshold
from src.tools.gateway import PolicyViolation


@dataclass
class RoutingWorkflowState:
    budget_spec: Any
    budget: BudgetTracker
    started_at: str
    t0: float
    workflow_path: Path
    workflow: dict[str, Any]
    workflow_fingerprint: str
    approval_threshold_used: float


def routing_and_workflow_stage(
    *,
    stage_ctx: StageContext,
    run_ctx: RunContext,
    quarantined_workflows: set[str],
) -> RoutingWorkflowState:
    try:
        budget_spec = budget_runtime.parse_budget(stage_ctx.envelope)
    except ValueError as e:
        msg = str(e)
        if len(msg) > 240:
            msg = msg[:237] + "..."
        dlq_path = dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="BUDGET",
            error_code="BUDGET_INVALID",
            message=msg or "Budget invalid.",
            envelope=stage_ctx.envelope,
        )
        print_error(
            "BUDGET_INVALID",
            "Budget invalid.",
            details={"message": msg, "dlq_file": dlq_path.name, "result_state": "FAILED"},
        )
        raise SystemExit(2)

    budget = BudgetTracker(budget_spec)
    started_at = dlq.iso_utc_now()
    t0 = time.perf_counter()

    strategy_path = stage_ctx.workspace / "orchestrator" / "strategy_table.v1.json"
    intent_registry_schema_path = stage_ctx.workspace / "schemas" / "intent-registry.schema.json"
    try:
        validation.validate_strategy_table_intents(
            strategy_path, intent_registry_schema_path=intent_registry_schema_path
        )
    except ValueError as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="STRATEGY_VALIDATE",
            error_code="STRATEGY_INVALID",
            message="Strategy table failed intent-registry validation.",
            envelope=stage_ctx.envelope,
        )
        details = json.loads(str(e))
        print_error("INVALID_STRATEGY_TABLE", "Strategy table failed intent-registry validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="STRATEGY_VALIDATE",
            error_code="STRATEGY_INVALID",
            message="Strategy table validation could not be performed.",
            envelope=stage_ctx.envelope,
        )
        print_error(
            "INVALID_STRATEGY_TABLE",
            "Strategy table validation could not be performed.",
            details={"strategy_table_path": str(strategy_path), "error": str(e)},
        )
        raise SystemExit(2)

    try:
        st = load_strategy_table(strategy_path)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="STRATEGY_VALIDATE",
            error_code="STRATEGY_INVALID",
            message="Strategy table is invalid.",
            envelope=stage_ctx.envelope,
        )
        print_error(
            "INVALID_STRATEGY_TABLE",
            "Strategy table is invalid.",
            details={"strategy_table_path": str(strategy_path), "error": str(e)},
        )
        raise SystemExit(2)

    if not run_ctx.intent:
        print_error(
            "INVALID_ENVELOPE",
            "Envelope missing intent.",
            details={"envelope_path": str(stage_ctx.envelope_path)},
        )
        raise SystemExit(2)

    run_ctx.workflow_id = route_intent(st, run_ctx.intent)
    if run_ctx.workflow_id and run_ctx.workflow_id in quarantined_workflows:
        run_ctx.governor_quarantine_hit = "WORKFLOW"
        e = PolicyViolation("QUARANTINED_WORKFLOW", f"Workflow is quarantined: {run_ctx.workflow_id}")
        msg = f"{e.error_code}: {e}"
        dlq_path = dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="GOVERNOR",
            error_code="POLICY_VIOLATION",
            message=msg,
            envelope=stage_ctx.envelope,
            workflow_id=run_ctx.workflow_id,
        )
        print_error(
            "GOVERNOR_BLOCK",
            "Governor blocked run.",
            details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
        )
        raise SystemExit(1)

    if not run_ctx.workflow_id:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="ROUTE",
            error_code="UNKNOWN_INTENT",
            message="Unknown intent; no route found in strategy table.",
            envelope=stage_ctx.envelope,
        )
        run_id = idempotency.timestamp_run_id()

        evidence = EvidenceWriter(out_dir=stage_ctx.out_dir, run_id=run_id)
        evidence.write_request(stage_ctx.envelope)
        finished_at = dlq.iso_utc_now()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        budget_usage = budget_runtime.budget_usage_dict(budget, fallback_elapsed_ms=duration_ms)
        summary = {
            "run_id": run_id,
            "request_id": run_ctx.request_id,
            "tenant_id": run_ctx.tenant_id,
            "workflow_id": None,
            "result_state": "FAILED",
            "status": "BLOCKED",
            "approval_threshold_used": read_approval_threshold(
                stage_ctx.workspace / "orchestrator" / "decision_policy.v1.json", default=0.7
            ),
            "threshold_used": read_approval_threshold(
                stage_ctx.workspace / "orchestrator" / "decision_policy.v1.json", default=0.7
            ),
            "risk_score": run_ctx.risk_score,
            "reason": "unknown_intent",
            "intent": run_ctx.intent,
            "dry_run": run_ctx.dry_run,
            "provider_used": "stub",
            "model_used": None,
            "secrets_used": [],
            "workflow_fingerprint": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": None,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "budget": budget_runtime.budget_spec_dict(budget_spec),
            "budget_usage": budget_usage,
            "budget_hit": None,
            "governor_mode_used": run_ctx.governor_mode_used,
            "governor_quarantine_hit": run_ctx.governor_quarantine_hit,
            "governor_concurrency_limit_hit": run_ctx.governor_concurrency_limit_hit,
        }
        if stage_ctx.replay_of is not None:
            summary["replay_of"] = stage_ctx.replay_of
            summary["replay_warnings"] = list(stage_ctx.replay_warnings)
        attach_trace_meta(summary, workspace=stage_ctx.workspace, out_dir=stage_ctx.out_dir, run_id=run_id)
        evidence.write_summary(summary)
        evidence.write_provenance(workspace=stage_ctx.workspace, summary=summary)
        evidence.write_integrity_manifest()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit(2)

    try:
        workflow_path, workflow = validation.load_workflow_by_id(stage_ctx.workspace, run_ctx.workflow_id)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="WORKFLOW_VALIDATE",
            error_code="WORKFLOW_INVALID",
            message="Failed to load workflow.",
            envelope=stage_ctx.envelope,
            workflow_id=run_ctx.workflow_id,
        )
        print_error(
            "INVALID_WORKFLOW",
            "Failed to load workflow.",
            details={"workflow_id": run_ctx.workflow_id, "error": str(e)},
        )
        raise SystemExit(2)

    try:
        validation.validate_workflow(workflow, workflow_path=workflow_path)
    except ValueError as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="WORKFLOW_VALIDATE",
            error_code="WORKFLOW_INVALID",
            message="Workflow failed internal validation.",
            envelope=stage_ctx.envelope,
            workflow_id=run_ctx.workflow_id,
        )
        details = json.loads(str(e))
        print_error("INVALID_WORKFLOW", "Workflow failed internal validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="WORKFLOW_VALIDATE",
            error_code="WORKFLOW_INVALID",
            message="Workflow validation could not be performed.",
            envelope=stage_ctx.envelope,
            workflow_id=run_ctx.workflow_id,
        )
        print_error(
            "INVALID_WORKFLOW",
            "Workflow validation could not be performed.",
            details={"workflow_id": run_ctx.workflow_id, "workflow_path": str(workflow_path), "error": str(e)},
        )
        raise SystemExit(2)

    workflow_fingerprint = validation.workflow_fingerprint(workflow, workflow_path)

    decision_policy_path = stage_ctx.workspace / "orchestrator" / "decision_policy.v1.json"
    approval_threshold_used = read_approval_threshold(decision_policy_path, default=0.7)

    if stage_ctx.replay_of and stage_ctx.replay_provenance:
        stored_fps_raw = stage_ctx.replay_provenance.get("fingerprints")
        stored_fps = stored_fps_raw if isinstance(stored_fps_raw, dict) else {}

        stored_wf_fp = stored_fps.get("workflow_fingerprint")
        if isinstance(stored_wf_fp, str) and stored_wf_fp and stored_wf_fp != workflow_fingerprint:
            stage_ctx.replay_warnings.append("WORKFLOW_FINGERPRINT_CHANGED")

        stored_policies_hash = stored_fps.get("policies_hash")
        if isinstance(stored_policies_hash, str) and stored_policies_hash:
            current_policies_hash = hash_json_dir(stage_ctx.workspace, "policies")
            if stored_policies_hash != current_policies_hash:
                stage_ctx.replay_warnings.append("POLICIES_CHANGED")

    return RoutingWorkflowState(
        budget_spec=budget_spec,
        budget=budget,
        started_at=started_at,
        t0=t0,
        workflow_path=workflow_path,
        workflow=workflow,
        workflow_fingerprint=workflow_fingerprint,
        approval_threshold_used=approval_threshold_used,
    )
