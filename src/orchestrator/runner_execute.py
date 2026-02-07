from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator import autonomy, budget_runtime, dlq, idempotency, quota, runner_config, validation
from src.orchestrator.executor_adapters import resolve_executor_port
from src.orchestrator.observability.otel_bridge import attach_trace_meta
from src.orchestrator.route import load_strategy_table, route_intent
from src.orchestrator.runner_inputs import ReplayContext
from src.orchestrator.runner_utils import hash_json_dir, print_error, replay_forced_run_id, safe_float
from src.orchestrator.workflow_exec import BudgetTracker, read_approval_threshold
from src.tools.gateway import PolicyViolation
from src.utils.jsonio import load_json


def run_envelope(
    *,
    envelope: dict[str, Any],
    envelope_path: Path,
    workspace: Path,
    out_dir: Path,
    replay_ctx: ReplayContext,
) -> None:
    replay_of = replay_ctx.replay_of
    replay_provenance = replay_ctx.replay_provenance
    replay_warnings = replay_ctx.replay_warnings
    force_new_run = replay_ctx.force_new_run
    replay_force_new_run = replay_ctx.replay_force_new_run

    envelope_schema_path = workspace / "schemas" / "request-envelope.schema.json"
    try:
        validation.validate_envelope(envelope, schema_path=envelope_schema_path, envelope_path=envelope_path)
    except ValueError as e:
        details = json.loads(str(e))
        errors = details.get("errors", [])
        budget_only = (
            isinstance(errors, list)
            and errors
            and all(isinstance(err, dict) and str(err.get("path", "")).startswith("$.budget") for err in errors)
        )
        if budget_only:
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="BUDGET",
                error_code="BUDGET_INVALID",
                message="Budget failed schema validation.",
                envelope=envelope,
            )
            print_error(
                "BUDGET_INVALID",
                "Budget failed schema validation.",
                details={
                    "envelope_path": str(envelope_path),
                    "errors": errors[:10],
                    "dlq_file": dlq_path.name,
                    "result_state": "FAILED",
                },
            )
            raise SystemExit(2)

        dlq.write_dlq_record(
            workspace=workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope failed schema validation.",
            envelope=envelope,
        )
        print_error("INVALID_ENVELOPE_SCHEMA", "Envelope failed schema validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope schema validation could not be performed.",
            envelope=envelope,
        )
        print_error(
            "INVALID_ENVELOPE_SCHEMA",
            "Envelope schema validation could not be performed.",
            details={"envelope_path": str(envelope_path), "schema_path": str(envelope_schema_path), "error": str(e)},
        )
        raise SystemExit(2)

    governor = runner_config.load_governor(workspace)
    governor_mode_used = governor.get("global_mode", "normal")
    quarantine = governor.get("quarantine") if isinstance(governor.get("quarantine"), dict) else {}
    quarantined_intents = set(x for x in quarantine.get("intents", []) if isinstance(x, str) and x)
    quarantined_workflows = set(x for x in quarantine.get("workflows", []) if isinstance(x, str) and x)
    conc = governor.get("concurrency") if isinstance(governor.get("concurrency"), dict) else {}
    max_parallel_runs_raw = conc.get("max_parallel_runs", 1)
    try:
        max_parallel_runs = int(max_parallel_runs_raw)
    except Exception:
        max_parallel_runs = 1
    if max_parallel_runs < 1:
        max_parallel_runs = 1

    lock_path = workspace / ".cache" / "governor_lock"
    lock_acquired = False
    governor_concurrency_limit_hit = False
    try:
        lock_path, lock_acquired = runner_config.acquire_governor_lock(
            workspace, max_parallel_runs=max_parallel_runs
        )
    except PolicyViolation as e:
        governor_concurrency_limit_hit = True
        msg = f"{e.error_code}: {e}"
        if len(msg) > 240:
            msg = msg[:237] + "..."
        dlq_path = dlq.write_dlq_record(
            workspace=workspace,
            stage="GOVERNOR",
            error_code="POLICY_VIOLATION",
            message=msg or "Governor blocked run.",
            envelope=envelope,
        )
        print_error(
            "GOVERNOR_BLOCK",
            "Governor blocked run.",
            details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
        )
        raise SystemExit(1)

    writes_allowed = governor_mode_used != "report_only"
    governor_quarantine_hit: str | None = None

    try:
        intent = envelope.get("intent")
        if isinstance(intent, str) and intent in quarantined_intents:
            governor_quarantine_hit = "INTENT"
            e = PolicyViolation("QUARANTINED_INTENT", f"Intent is quarantined: {intent}")
            msg = f"{e.error_code}: {e}"
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="GOVERNOR",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
            )
            print_error(
                "GOVERNOR_BLOCK",
                "Governor blocked run.",
                details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
            )
            raise SystemExit(1)

        try:
            budget_spec = budget_runtime.parse_budget(envelope)
        except ValueError as e:
            msg = str(e)
            if len(msg) > 240:
                msg = msg[:237] + "..."
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="BUDGET",
                error_code="BUDGET_INVALID",
                message=msg or "Budget invalid.",
                envelope=envelope,
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

        strategy_path = workspace / "orchestrator" / "strategy_table.v1.json"
        intent_registry_schema_path = workspace / "schemas" / "intent-registry.schema.json"
        try:
            validation.validate_strategy_table_intents(
                strategy_path, intent_registry_schema_path=intent_registry_schema_path
            )
        except ValueError as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="STRATEGY_VALIDATE",
                error_code="STRATEGY_INVALID",
                message="Strategy table failed intent-registry validation.",
                envelope=envelope,
            )
            details = json.loads(str(e))
            print_error("INVALID_STRATEGY_TABLE", "Strategy table failed intent-registry validation.", details=details)
            raise SystemExit(2)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="STRATEGY_VALIDATE",
                error_code="STRATEGY_INVALID",
                message="Strategy table validation could not be performed.",
                envelope=envelope,
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
                workspace=workspace,
                stage="STRATEGY_VALIDATE",
                error_code="STRATEGY_INVALID",
                message="Strategy table is invalid.",
                envelope=envelope,
            )
            print_error(
                "INVALID_STRATEGY_TABLE",
                "Strategy table is invalid.",
                details={"strategy_table_path": str(strategy_path), "error": str(e)},
            )
            raise SystemExit(2)

        intent = envelope.get("intent")
        if not isinstance(intent, str) or not intent:
            print_error(
                "INVALID_ENVELOPE",
                "Envelope missing intent.",
                details={"envelope_path": str(envelope_path)},
            )
            raise SystemExit(2)

        risk_score = safe_float(envelope.get("risk_score", 0.0), default=0.0)
        dry_run = bool(envelope.get("dry_run", False))
        request_id = str(envelope.get("request_id", ""))
        tenant_id = str(envelope.get("tenant_id", ""))
        idempotency_key = envelope.get("idempotency_key")

        workflow_id = route_intent(st, intent)
        if workflow_id and workflow_id in quarantined_workflows:
            governor_quarantine_hit = "WORKFLOW"
            e = PolicyViolation("QUARANTINED_WORKFLOW", f"Workflow is quarantined: {workflow_id}")
            msg = f"{e.error_code}: {e}"
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="GOVERNOR",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
                workflow_id=workflow_id,
            )
            print_error(
                "GOVERNOR_BLOCK",
                "Governor blocked run.",
                details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
            )
            raise SystemExit(1)

        if not workflow_id:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="ROUTE",
                error_code="UNKNOWN_INTENT",
                message="Unknown intent; no route found in strategy table.",
                envelope=envelope,
            )
            run_id = idempotency.timestamp_run_id()

            evidence = EvidenceWriter(out_dir=out_dir, run_id=run_id)
            evidence.write_request(envelope)
            finished_at = dlq.iso_utc_now()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            budget_usage = budget_runtime.budget_usage_dict(budget, fallback_elapsed_ms=duration_ms)
            summary = {
                "run_id": run_id,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "workflow_id": None,
                "result_state": "FAILED",
                "status": "BLOCKED",
                "approval_threshold_used": read_approval_threshold(
                    workspace / "orchestrator" / "decision_policy.v1.json", default=0.7
                ),
                "threshold_used": read_approval_threshold(
                    workspace / "orchestrator" / "decision_policy.v1.json", default=0.7
                ),
                "risk_score": risk_score,
                "reason": "unknown_intent",
                "intent": intent,
                "dry_run": dry_run,
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
                "governor_mode_used": governor_mode_used,
                "governor_quarantine_hit": governor_quarantine_hit,
                "governor_concurrency_limit_hit": governor_concurrency_limit_hit,
            }
            if replay_of is not None:
                summary["replay_of"] = replay_of
                summary["replay_warnings"] = list(replay_warnings)
            attach_trace_meta(summary, workspace=workspace, out_dir=out_dir, run_id=run_id)
            evidence.write_summary(summary)
            evidence.write_provenance(workspace=workspace, summary=summary)
            evidence.write_integrity_manifest()
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            raise SystemExit(2)

        try:
            workflow_path, workflow = validation.load_workflow_by_id(workspace, workflow_id)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="WORKFLOW_VALIDATE",
                error_code="WORKFLOW_INVALID",
                message="Failed to load workflow.",
                envelope=envelope,
                workflow_id=workflow_id,
            )
            print_error(
                "INVALID_WORKFLOW",
                "Failed to load workflow.",
                details={"workflow_id": workflow_id, "error": str(e)},
            )
            raise SystemExit(2)

        try:
            validation.validate_workflow(workflow, workflow_path=workflow_path)
        except ValueError as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="WORKFLOW_VALIDATE",
                error_code="WORKFLOW_INVALID",
                message="Workflow failed internal validation.",
                envelope=envelope,
                workflow_id=workflow_id,
            )
            details = json.loads(str(e))
            print_error("INVALID_WORKFLOW", "Workflow failed internal validation.", details=details)
            raise SystemExit(2)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="WORKFLOW_VALIDATE",
                error_code="WORKFLOW_INVALID",
                message="Workflow validation could not be performed.",
                envelope=envelope,
                workflow_id=workflow_id,
            )
            print_error(
                "INVALID_WORKFLOW",
                "Workflow validation could not be performed.",
                details={"workflow_id": workflow_id, "workflow_path": str(workflow_path), "error": str(e)},
            )
            raise SystemExit(2)

        workflow_fingerprint = validation.workflow_fingerprint(workflow, workflow_path)

        decision_policy_path = workspace / "orchestrator" / "decision_policy.v1.json"
        approval_threshold_used = read_approval_threshold(decision_policy_path, default=0.7)

        if replay_of and replay_provenance:
            stored_fps_raw = replay_provenance.get("fingerprints")
            stored_fps = stored_fps_raw if isinstance(stored_fps_raw, dict) else {}

            stored_wf_fp = stored_fps.get("workflow_fingerprint")
            if isinstance(stored_wf_fp, str) and stored_wf_fp and stored_wf_fp != workflow_fingerprint:
                replay_warnings.append("WORKFLOW_FINGERPRINT_CHANGED")

            stored_policies_hash = stored_fps.get("policies_hash")
            if isinstance(stored_policies_hash, str) and stored_policies_hash:
                current_policies_hash = hash_json_dir(workspace, "policies")
                if stored_policies_hash != current_policies_hash:
                    replay_warnings.append("POLICIES_CHANGED")

        idempotency_key_hash: str | None = None
        store_key_id: str | None = None

        tenant_id_raw = envelope.get("tenant_id")
        if (
            isinstance(tenant_id_raw, str)
            and tenant_id_raw
            and isinstance(idempotency_key, str)
            and idempotency_key
        ):
            key_plain = f"{tenant_id_raw}:{idempotency_key}:{workflow_id}"
            idempotency_key_hash = sha256(key_plain.encode("utf-8")).hexdigest()
            if replay_force_new_run:
                run_id = replay_forced_run_id(replay_of=replay_of or request_id or "unknown")
            elif force_new_run:
                # Envelope runs: force a new run_id without touching idempotency mappings.
                run_id = idempotency.timestamp_run_id()
            else:
                store_key_id = idempotency_key_hash[:24]
                run_id = idempotency.deterministic_run_id(
                    tenant_id=tenant_id_raw,
                    idempotency_key=idempotency_key,
                    workflow_id=workflow_id,
                    workflow_fingerprint=workflow_fingerprint,
                )
        else:
            run_id = (
                replay_forced_run_id(replay_of=replay_of or request_id or "unknown")
                if replay_force_new_run
                else idempotency.timestamp_run_id()
            )

        store_path = workspace / ".cache" / "idempotency_store.v1.json"
        mappings, migrated = idempotency.load_idempotency_store(store_path)
        changed = migrated
        if store_key_id:
            if mappings.get(store_key_id) != run_id:
                mappings[store_key_id] = run_id
                changed = True
            if changed or not store_path.exists():
                idempotency.save_idempotency_store(store_path, mappings)

            summary_path = out_dir / run_id / "summary.json"
            if idempotency.read_result_state(summary_path) == "COMPLETED":
                payload = {
                    "status": "IDEMPOTENT_HIT",
                    "message": "IDEMPOTENT_HIT",
                    "run_id": run_id,
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "workflow_fingerprint": workflow_fingerprint,
                    "approval_threshold_used": approval_threshold_used,
                    "idempotency_key_hash": idempotency_key_hash,
                    "governor_mode_used": governor_mode_used,
                    "governor_quarantine_hit": governor_quarantine_hit,
                    "governor_concurrency_limit_hit": governor_concurrency_limit_hit,
                }
                if replay_of is not None:
                    payload["replay_of"] = replay_of
                    payload["replay_warnings"] = list(replay_warnings)
                print(
                    json.dumps(
                        payload,
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return

        quota_policy = runner_config.load_quota_policy(workspace)
        quota_store_path = workspace / ".cache" / "tenant_quota_store.v1.json"
        quota_date = quota.utc_date_key()
        quota_store = quota.load_quota_store(quota_store_path)
        runs_used_before, est_tokens_used_before = quota.get_quota_usage(
            quota_store, date_key=quota_date, tenant_id=tenant_id
        )
        max_runs_per_day, max_est_tokens_per_day = quota.quota_limits_for_tenant(quota_policy, tenant_id)
        quota_spec = {"max_runs_per_day": max_runs_per_day, "max_est_tokens_per_day": max_est_tokens_per_day}
        quota_usage_before = {"runs_used": runs_used_before, "est_tokens_used": est_tokens_used_before}
        quota_usage_after = dict(quota_usage_before)
        quota_store_updated = False

        autonomy_policy = runner_config.load_autonomy_policy(workspace)
        autonomy_cfg = autonomy.autonomy_cfg_for_intent(autonomy_policy, intent)
        autonomy_store_path = workspace / ".cache" / "autonomy_store.v1.json"
        autonomy_store = autonomy.load_autonomy_store(autonomy_store_path)
        autonomy_record = autonomy.autonomy_record_for_intent(
            autonomy_store, intent, initial_mode=str(autonomy_cfg.get("mode", "human_review"))
        )
        autonomy_mode_used = autonomy_record.get("mode", "human_review")

        side_effect_policy = envelope.get("side_effect_policy", "none")
        side_effect_policy = side_effect_policy if isinstance(side_effect_policy, str) else "none"

        autonomy_gate_triggered = autonomy.autonomy_gate_triggered(
            autonomy_mode_used=str(autonomy_mode_used),
            dry_run=bool(dry_run),
            side_effect_policy=str(side_effect_policy),
        )

        if int(runs_used_before) + 1 > int(max_runs_per_day):
            msg = (
                "QUOTA_RUNS_EXCEEDED: "
                f"runs_used {int(runs_used_before)} + 1 > max_runs_per_day {int(max_runs_per_day)}"
            )
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="QUOTA",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
                workflow_id=workflow_id,
            )

            evidence = EvidenceWriter(out_dir=out_dir, run_id=run_id)
            evidence.write_request(envelope)

            finished_at = dlq.iso_utc_now()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            budget_usage = budget_runtime.budget_usage_dict(budget, fallback_elapsed_ms=duration_ms)

            updated_record = autonomy.update_autonomy_record(
                autonomy_record,
                outcome="FAIL",
                cfg_mode=str(autonomy_cfg.get("mode", "human_review")),
                success_threshold=float(autonomy_cfg.get("success_threshold", 0.8)),
                min_samples=int(autonomy_cfg.get("min_samples", 5)),
            )
            autonomy_store[intent] = updated_record
            autonomy.save_autonomy_store(autonomy_store_path, autonomy_store)
            autonomy_snapshot = {
                "samples": int(updated_record.get("samples", 0)),
                "successes": int(updated_record.get("successes", 0)),
                "mode": updated_record.get("mode"),
            }
            summary = {
                "run_id": run_id,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "result_state": "FAILED",
                "status": "FAILED",
                "approval_threshold_used": approval_threshold_used,
                "threshold_used": approval_threshold_used,
                "risk_score": risk_score,
                "intent": intent,
                "workflow_path": str(workflow_path),
                "dry_run": dry_run,
                "provider_used": "stub",
                "model_used": None,
                "secrets_used": [],
                "workflow_fingerprint": workflow_fingerprint,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "idempotency_key_hash": idempotency_key_hash,
                "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
                "budget": budget_runtime.budget_spec_dict(budget_spec),
                "budget_usage": budget_usage,
                "budget_hit": None,
                "quota": quota_spec,
                "quota_usage_before": quota_usage_before,
                "quota_usage_after": quota_usage_after,
                "quota_hit": "RUNS",
                "autonomy_mode_used": autonomy_mode_used,
                "autonomy_store_snapshot": autonomy_snapshot,
                "autonomy_gate_triggered": autonomy_gate_triggered,
                "governor_mode_used": governor_mode_used,
                "governor_quarantine_hit": governor_quarantine_hit,
                "governor_concurrency_limit_hit": governor_concurrency_limit_hit,
                "error_code": "POLICY_VIOLATION",
                "policy_violation_code": "QUOTA_RUNS_EXCEEDED",
                "error": msg,
                "dlq_file": dlq_path.name,
            }
            if replay_of is not None:
                summary["replay_of"] = replay_of
                summary["replay_warnings"] = list(replay_warnings)
            attach_trace_meta(summary, workspace=workspace, out_dir=out_dir, run_id=run_id)
            evidence.write_summary(summary)
            evidence.write_provenance(workspace=workspace, summary=summary)
            evidence.write_integrity_manifest()
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            raise SystemExit(1)

        quota.set_quota_usage(
            quota_store,
            date_key=quota_date,
            tenant_id=tenant_id,
            runs_used=int(runs_used_before) + 1,
            est_tokens_used=int(est_tokens_used_before),
        )
        quota.save_quota_store(quota_store_path, quota_store)
        quota_store_updated = True

        # Enforce token quota during execution (fail before side effects).
        budget.set_quota_context(
            max_est_tokens_per_day=max_est_tokens_per_day,
            est_tokens_used_before=est_tokens_used_before,
        )

        evidence = EvidenceWriter(out_dir=out_dir, run_id=run_id)
        evidence.write_request(envelope)

        executor = resolve_executor_port(workspace=workspace)
        provider_used_default = "stub"
        model_used_default = None

        try:
            exec_started_at = dlq.iso_utc_now()
            exec_t0 = time.perf_counter()
            exec_summary = executor.execute_workflow(
                envelope=envelope,
                workflow=workflow,
                workspace=workspace,
                evidence=evidence,
                approval_threshold=approval_threshold_used,
                writes_allowed=writes_allowed,
                budget=budget,
                force_suspend_reason=autonomy_gate_triggered,
            )
            finished_at = dlq.iso_utc_now()
            duration_ms = int((time.perf_counter() - exec_t0) * 1000)
            budget_usage = budget_runtime.budget_usage_dict(budget, fallback_elapsed_ms=duration_ms)

            if quota_store_updated:
                est_tokens_after = int(est_tokens_used_before) + int(budget_usage.get("est_tokens_used", 0))
                quota.set_quota_usage(
                    quota_store,
                    date_key=quota_date,
                    tenant_id=tenant_id,
                    runs_used=int(runs_used_before) + 1,
                    est_tokens_used=est_tokens_after,
                )
                quota.save_quota_store(quota_store_path, quota_store)
                quota_usage_after = {"runs_used": int(runs_used_before) + 1, "est_tokens_used": est_tokens_after}

            provider_used = exec_summary.get("provider_used") or provider_used_default
            model_used = (
                exec_summary.get("model_used") if exec_summary.get("model_used") is not None else model_used_default
            )
            secrets_used = exec_summary.get("secrets_used", [])
            secrets_used_list = secrets_used if isinstance(secrets_used, list) else []

            summary = {
                "run_id": run_id,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "result_state": exec_summary.get("status"),
                "status": exec_summary.get("status"),
                "approval_threshold_used": approval_threshold_used,
                "threshold_used": approval_threshold_used,
                "risk_score": risk_score,
                "intent": intent,
                "workflow_path": str(workflow_path),
                "dry_run": dry_run,
                "provider_used": provider_used,
                "model_used": model_used,
                "secrets_used": secrets_used_list,
                "workflow_fingerprint": workflow_fingerprint,
                "started_at": exec_started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "idempotency_key_hash": idempotency_key_hash,
                "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
                "budget": budget_runtime.budget_spec_dict(budget_spec),
                "budget_usage": budget_usage,
                "budget_hit": None,
                "quota": quota_spec,
                "quota_usage_before": quota_usage_before,
                "quota_usage_after": quota_usage_after,
                "quota_hit": None,
                "governor_mode_used": governor_mode_used,
                "governor_quarantine_hit": governor_quarantine_hit,
                "governor_concurrency_limit_hit": governor_concurrency_limit_hit,
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
                    workspace=workspace,
                    stage=stage,
                    error_code="POLICY_VIOLATION",
                    message=msg or "Policy violation during execution.",
                    envelope=envelope,
                    workflow_id=workflow_id,
                )
            finished_at = dlq.iso_utc_now()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            budget_usage = budget_runtime.budget_usage_dict(budget, fallback_elapsed_ms=duration_ms)
            quota_hit = quota.quota_hit_from_policy_violation(e.error_code) if isinstance(e, PolicyViolation) else None

            if quota_store_updated:
                est_tokens_after = int(est_tokens_used_before) + int(budget_usage.get("est_tokens_used", 0))
                quota.set_quota_usage(
                    quota_store,
                    date_key=quota_date,
                    tenant_id=tenant_id,
                    runs_used=int(runs_used_before) + 1,
                    est_tokens_used=est_tokens_after,
                )
                quota.save_quota_store(quota_store_path, quota_store)
                quota_usage_after = {"runs_used": int(runs_used_before) + 1, "est_tokens_used": est_tokens_after}
            summary = {
                "run_id": run_id,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "result_state": "FAILED",
                "status": "FAILED",
                "approval_threshold_used": approval_threshold_used,
                "threshold_used": approval_threshold_used,
                "risk_score": risk_score,
                "intent": intent,
                "workflow_path": str(workflow_path),
                "dry_run": dry_run,
                "provider_used": provider_used_on_error,
                "model_used": model_used_on_error,
                "secrets_used": secrets_used_list,
                "workflow_fingerprint": workflow_fingerprint,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "idempotency_key_hash": idempotency_key_hash,
                "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
                "budget": budget_runtime.budget_spec_dict(budget_spec),
                "budget_usage": budget_usage,
                "budget_hit": budget_runtime.budget_hit_from_policy_violation(e.error_code)
                if isinstance(e, PolicyViolation)
                else None,
                "quota": quota_spec,
                "quota_usage_before": quota_usage_before,
                "quota_usage_after": quota_usage_after,
                "quota_hit": quota_hit,
                "governor_mode_used": governor_mode_used,
                "governor_quarantine_hit": governor_quarantine_hit,
                "governor_concurrency_limit_hit": governor_concurrency_limit_hit,
                "error_code": "POLICY_VIOLATION" if isinstance(e, PolicyViolation) else None,
                "policy_violation_code": e.error_code if isinstance(e, PolicyViolation) else None,
                "error": str(e),
            }

        if replay_of is not None:
            summary["replay_of"] = replay_of
            summary["replay_warnings"] = list(replay_warnings)

        # Progressive autonomy (v0.1): add evidence fields and update store on terminal outcomes.
        summary["autonomy_mode_used"] = autonomy_mode_used
        summary["autonomy_gate_triggered"] = autonomy_gate_triggered

        autonomy_outcome: str | None = None
        result_state = summary.get("result_state")
        if result_state == "COMPLETED" and summary.get("policy_violation_code") is None and summary.get("error_code") is None:
            autonomy_outcome = "SUCCESS"
        elif result_state == "FAILED":
            autonomy_outcome = "FAIL"

        if autonomy_outcome is not None:
            autonomy_record = autonomy.update_autonomy_record(
                autonomy_record,
                outcome=autonomy_outcome,
                cfg_mode=str(autonomy_cfg.get("mode", "human_review")),
                success_threshold=float(autonomy_cfg.get("success_threshold", 0.8)),
                min_samples=int(autonomy_cfg.get("min_samples", 5)),
            )
            autonomy_store[intent] = autonomy_record
            autonomy.save_autonomy_store(autonomy_store_path, autonomy_store)

        summary["autonomy_store_snapshot"] = {
            "samples": int(autonomy_record.get("samples", 0)),
            "successes": int(autonomy_record.get("successes", 0)),
            "mode": autonomy_record.get("mode"),
        }

        attach_trace_meta(summary, workspace=workspace, out_dir=out_dir, run_id=run_id)
        evidence.write_summary(summary)
        if summary.get("result_state") == "SUSPENDED":
            resume_path = evidence.run_dir
            try:
                resume_path = evidence.run_dir.resolve().relative_to(workspace.resolve())
            except ValueError:
                resume_path = evidence.run_dir

            suspend_reason = "APPROVAL_REQUIRED"
            if summary.get("autonomy_gate_triggered") in {"AUTONOMY_MANUAL_ONLY", "AUTONOMY_HUMAN_REVIEW"}:
                suspend_reason = str(summary.get("autonomy_gate_triggered"))
            evidence.write_suspend(
                {
                    "run_id": run_id,
                    "reason": suspend_reason,
                    "risk_score": risk_score,
                    "threshold_used": approval_threshold_used,
                    "next_action_hint": f"Resume with --resume {resume_path} --approve true",
                }
            )
        evidence.write_provenance(workspace=workspace, summary=summary)
        evidence.write_integrity_manifest()
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if summary.get("status") == "FAILED":
            raise SystemExit(1)
    finally:
        if lock_acquired:
            runner_config.release_governor_lock(lock_path)
