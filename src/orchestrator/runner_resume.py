from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator import autonomy, budget_runtime, dlq, quota, runner_config
from src.orchestrator.runner_utils import print_error
from src.orchestrator.workflow_exec import BudgetTracker, execute_mod_b_only
from src.tools.gateway import PolicyViolation
from src.utils.jsonio import load_json


def handle_resume(*, args: Any, workspace: Path, out_dir: Path) -> None:
    resume_in = Path(args.resume)
    resume_dir = (workspace / resume_in).resolve() if not resume_in.is_absolute() else resume_in.resolve()
    try:
        resume_dir.relative_to(workspace)
    except ValueError:
        print_error(
            "INVALID_RESUME_PATH",
            "--resume must be within --workspace for safety.",
            details={"resume_dir": str(resume_dir), "workspace": str(workspace)},
        )
        raise SystemExit(2)

    request_path = resume_dir / "request.json"
    summary_path = resume_dir / "summary.json"

    try:
        envelope = load_json(request_path)
    except Exception as e:
        print_error(
            "INVALID_RESUME_EVIDENCE",
            "Failed to load request.json from evidence directory.",
            details={"request_path": str(request_path), "error": str(e)},
        )
        raise SystemExit(2)

    try:
        summary_existing = load_json(summary_path)
    except Exception as e:
        print_error(
            "INVALID_RESUME_EVIDENCE",
            "Failed to load summary.json from evidence directory.",
            details={"summary_path": str(summary_path), "error": str(e)},
        )
        raise SystemExit(2)

    if not isinstance(summary_existing, dict):
        print_error(
            "INVALID_RESUME_EVIDENCE",
            "Evidence summary.json must be a JSON object.",
            details={"summary_path": str(summary_path)},
        )
        raise SystemExit(2)

    run_id = summary_existing.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        run_id = resume_dir.name

    if summary_existing.get("result_state") != "SUSPENDED":
        print_error(
            "NOT_SUSPENDED",
            "Only SUSPENDED runs can be resumed.",
            details={"run_id": run_id, "result_state": summary_existing.get("result_state")},
        )
        raise SystemExit(2)

    if not args.approve:
        print(
            json.dumps(
                {"status": "APPROVAL_REQUIRED", "message": "APPROVAL_REQUIRED", "run_id": run_id},
                indent=2,
                ensure_ascii=False,
            )
        )
        raise SystemExit(3)

    mod_a_output_path = resume_dir / "nodes" / "MOD_A" / "output.json"
    try:
        mod_a_output = load_json(mod_a_output_path)
    except Exception as e:
        print_error(
            "INVALID_RESUME_EVIDENCE",
            "Missing or invalid MOD_A output in evidence; cannot resume MOD_B.",
            details={"mod_a_output_path": str(mod_a_output_path), "error": str(e)},
        )
        raise SystemExit(2)

    if not isinstance(mod_a_output, dict):
        print_error(
            "INVALID_RESUME_EVIDENCE",
            "MOD_A output.json must be a JSON object.",
            details={"mod_a_output_path": str(mod_a_output_path)},
        )
        raise SystemExit(2)

    governor = runner_config.load_governor(workspace)
    governor_mode_used = governor.get("global_mode", "normal")
    quarantine = governor.get("quarantine") if isinstance(governor.get("quarantine"), dict) else {}
    quarantined_intents = set(x for x in quarantine.get("intents", []) if isinstance(x, str) and x)
    quarantined_workflows = set(x for x in quarantine.get("workflows", []) if isinstance(x, str) and x)
    conc = governor.get("concurrency") if isinstance(governor.get("concurrency"), dict) else {}
    max_parallel_runs = int(conc.get("max_parallel_runs", 1)) if isinstance(conc.get("max_parallel_runs", 1), int) else 1
    writes_allowed = governor_mode_used != "report_only"

    workflow_id_resume = summary_existing.get("workflow_id")
    workflow_id_resume = workflow_id_resume if isinstance(workflow_id_resume, str) and workflow_id_resume else None

    lock_path = workspace / ".cache" / "governor_lock"
    lock_acquired = False
    try:
        try:
            lock_path, lock_acquired = runner_config.acquire_governor_lock(
                workspace, max_parallel_runs=max_parallel_runs
            )
        except PolicyViolation as e:
            msg = f"{e.error_code}: {e}"
            if len(msg) > 240:
                msg = msg[:237] + "..."
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="GOVERNOR",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
                workflow_id=workflow_id_resume,
            )
            print_error(
                "GOVERNOR_BLOCK",
                "Governor blocked resume.",
                details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
            )
            raise SystemExit(1)

        intent_resume = envelope.get("intent")
        if isinstance(intent_resume, str) and intent_resume in quarantined_intents:
            e = PolicyViolation("QUARANTINED_INTENT", f"Intent is quarantined: {intent_resume}")
            msg = f"{e.error_code}: {e}"
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="GOVERNOR",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
                workflow_id=workflow_id_resume,
            )
            print_error(
                "GOVERNOR_BLOCK",
                "Governor blocked resume.",
                details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
            )
            raise SystemExit(1)

        if workflow_id_resume and workflow_id_resume in quarantined_workflows:
            e = PolicyViolation("QUARANTINED_WORKFLOW", f"Workflow is quarantined: {workflow_id_resume}")
            msg = f"{e.error_code}: {e}"
            dlq_path = dlq.write_dlq_record(
                workspace=workspace,
                stage="GOVERNOR",
                error_code="POLICY_VIOLATION",
                message=msg,
                envelope=envelope,
                workflow_id=workflow_id_resume,
            )
            print_error(
                "GOVERNOR_BLOCK",
                "Governor blocked resume.",
                details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
            )
            raise SystemExit(1)

        evidence = EvidenceWriter(out_dir=out_dir, run_id=resume_dir.name)
        resumed_at = dlq.iso_utc_now()

        try:
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
                    workflow_id=workflow_id_resume,
                )
                print_error(
                    "BUDGET_INVALID",
                    "Budget invalid on resume.",
                    details={"message": msg, "dlq_file": dlq_path.name, "result_state": "FAILED"},
                )
                raise SystemExit(2)

            budget = BudgetTracker(budget_spec)
            existing_usage = summary_existing.get("budget_usage") if isinstance(summary_existing, dict) else None
            if isinstance(existing_usage, dict):
                try:
                    budget.usage.attempts_used = int(existing_usage.get("attempts_used", 0))
                except Exception:
                    budget.usage.attempts_used = 0
                try:
                    budget.usage.est_tokens_used = int(existing_usage.get("est_tokens_used", 0))
                except Exception:
                    budget.usage.est_tokens_used = 0
                try:
                    prev_elapsed_ms = int(existing_usage.get("elapsed_ms", 0))
                except Exception:
                    prev_elapsed_ms = 0
                if prev_elapsed_ms > 0:
                    setattr(budget, "_t0", time.monotonic() - (prev_elapsed_ms / 1000.0))

            budget.checkpoint_time()
            res = execute_mod_b_only(
                envelope=envelope,
                mod_a_output=mod_a_output,
                workspace=workspace,
                evidence=evidence,
                node_id="MOD_B",
                writes_allowed=writes_allowed,
                budget=budget,
            )
            budget.update_elapsed()
            finished_at = dlq.iso_utc_now()

            nodes_existing = summary_existing.get("nodes")
            nodes: list[dict[str, Any]] = []
            if isinstance(nodes_existing, list):
                for n in nodes_existing:
                    if isinstance(n, dict) and n.get("node_id") != res.node_id:
                        nodes.append(n)
            nodes.append({"node_id": res.node_id, "status": res.status, "output": res.output})

            updated = dict(summary_existing)
            updated["resumed"] = True
            updated["resumed_at"] = resumed_at
            updated["result_state"] = "COMPLETED" if res.status == "COMPLETED" else "FAILED"
            updated["status"] = updated["result_state"]
            updated["finished_at"] = finished_at
            updated["duration_ms"] = budget_runtime.duration_ms_from_started(
                updated.get("started_at"), finished_at, fallback=updated.get("duration_ms")
            )
            updated["nodes"] = nodes
            updated["governor_mode_used"] = governor_mode_used
            updated["governor_quarantine_hit"] = None
            updated["governor_concurrency_limit_hit"] = False
            updated["budget"] = budget_runtime.budget_spec_dict(budget_spec)
            updated["budget_usage"] = budget_runtime.budget_usage_dict(
                budget, fallback_elapsed_ms=updated.get("duration_ms", 0)
            )
            updated["budget_hit"] = None

            intent_str = intent_resume if isinstance(intent_resume, str) and intent_resume else ""
            if intent_str:
                autonomy_policy = runner_config.load_autonomy_policy(workspace)
                autonomy_cfg = autonomy.autonomy_cfg_for_intent(autonomy_policy, intent_str)
                autonomy_store_path = workspace / ".cache" / "autonomy_store.v1.json"
                autonomy_store = autonomy.load_autonomy_store(autonomy_store_path)
                autonomy_record = autonomy.autonomy_record_for_intent(
                    autonomy_store, intent_str, initial_mode=str(autonomy_cfg.get("mode", "human_review"))
                )
                autonomy_mode_used = autonomy_record.get("mode", "human_review")

                autonomy_outcome = "SUCCESS" if updated.get("result_state") == "COMPLETED" else "FAIL"
                autonomy_record = autonomy.update_autonomy_record(
                    autonomy_record,
                    outcome=autonomy_outcome,
                    cfg_mode=str(autonomy_cfg.get("mode", "human_review")),
                    success_threshold=float(autonomy_cfg.get("success_threshold", 0.8)),
                    min_samples=int(autonomy_cfg.get("min_samples", 5)),
                )
                autonomy_store[intent_str] = autonomy_record
                autonomy.save_autonomy_store(autonomy_store_path, autonomy_store)

                updated["autonomy_mode_used"] = autonomy_mode_used
                updated["autonomy_gate_triggered"] = None
                updated["autonomy_store_snapshot"] = {
                    "samples": int(autonomy_record.get("samples", 0)),
                    "successes": int(autonomy_record.get("successes", 0)),
                    "mode": autonomy_record.get("mode"),
                }

            evidence.write_summary(updated)
            evidence.write_resume_log(f"{resumed_at} RESUME approve=true\n")
            evidence.write_provenance(workspace=workspace, summary=updated)
            evidence.write_integrity_manifest()

            print(json.dumps(updated, indent=2, ensure_ascii=False))
            if updated["result_state"] != "COMPLETED":
                raise SystemExit(1)
            return
        except SystemExit:
            raise
        except Exception as e:
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
                    workflow_id=workflow_id_resume,
                )
            finished_at = dlq.iso_utc_now()
            updated = dict(summary_existing)
            updated["resumed"] = True
            updated["resumed_at"] = resumed_at
            updated["result_state"] = "FAILED"
            updated["status"] = "FAILED"
            updated["finished_at"] = finished_at
            updated["duration_ms"] = budget_runtime.duration_ms_from_started(
                updated.get("started_at"), finished_at, fallback=updated.get("duration_ms")
            )
            updated["resume_error"] = str(e)
            updated["governor_mode_used"] = governor_mode_used
            updated["governor_quarantine_hit"] = None
            updated["governor_concurrency_limit_hit"] = False
            if isinstance(e, PolicyViolation):
                updated["error_code"] = "POLICY_VIOLATION"
                updated["policy_violation_code"] = e.error_code
                updated["budget_hit"] = budget_runtime.budget_hit_from_policy_violation(e.error_code)
            else:
                updated["budget_hit"] = None
            if "budget_spec" in locals():
                updated["budget"] = budget_runtime.budget_spec_dict(budget_spec)
            if "budget" in locals():
                updated["budget_usage"] = budget_runtime.budget_usage_dict(
                    budget, fallback_elapsed_ms=updated.get("duration_ms", 0)
                )

            intent_str = intent_resume if isinstance(intent_resume, str) and intent_resume else ""
            if intent_str:
                autonomy_policy = runner_config.load_autonomy_policy(workspace)
                autonomy_cfg = autonomy.autonomy_cfg_for_intent(autonomy_policy, intent_str)
                autonomy_store_path = workspace / ".cache" / "autonomy_store.v1.json"
                autonomy_store = autonomy.load_autonomy_store(autonomy_store_path)
                autonomy_record = autonomy.autonomy_record_for_intent(
                    autonomy_store, intent_str, initial_mode=str(autonomy_cfg.get("mode", "human_review"))
                )
                autonomy_mode_used = autonomy_record.get("mode", "human_review")

                autonomy_record = autonomy.update_autonomy_record(
                    autonomy_record,
                    outcome="FAIL",
                    cfg_mode=str(autonomy_cfg.get("mode", "human_review")),
                    success_threshold=float(autonomy_cfg.get("success_threshold", 0.8)),
                    min_samples=int(autonomy_cfg.get("min_samples", 5)),
                )
                autonomy_store[intent_str] = autonomy_record
                autonomy.save_autonomy_store(autonomy_store_path, autonomy_store)

                updated["autonomy_mode_used"] = autonomy_mode_used
                updated["autonomy_gate_triggered"] = None
                updated["autonomy_store_snapshot"] = {
                    "samples": int(autonomy_record.get("samples", 0)),
                    "successes": int(autonomy_record.get("successes", 0)),
                    "mode": autonomy_record.get("mode"),
                }

            evidence.write_summary(updated)
            evidence.write_resume_log(f"{resumed_at} RESUME_FAILED {str(e)}\n")
            evidence.write_provenance(workspace=workspace, summary=updated)
            evidence.write_integrity_manifest()
            print_error("RESUME_FAILED", "Resume failed.", details={"run_id": run_id, "error": str(e)})
            raise SystemExit(1)
    finally:
        if lock_acquired:
            runner_config.release_governor_lock(lock_path)
