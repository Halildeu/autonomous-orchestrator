from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator import autonomy, budget_runtime, dlq, idempotency, quota, runner_config, validation
from src.orchestrator.route import load_strategy_table, route_intent
from src.orchestrator.workflow_exec import BudgetTracker, execute_mod_b_only, execute_workflow, read_approval_threshold
from src.providers.openai_provider import DeterministicStubProvider
from src.tools.gateway import PolicyViolation
from src.utils.jsonio import load_json


def _print_error(kind: str, message: str, *, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"status": "ERROR", "error_type": kind, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sha256_concat_files(paths: list[Path]) -> str:
    h = sha256()
    for p in paths:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def _hash_json_dir(workspace: Path, rel_dir: str) -> str:
    d = workspace / rel_dir
    paths: list[Path] = []
    if d.exists():
        paths = [p for p in d.glob("*.json") if p.is_file()]
    paths = sorted(paths, key=lambda p: p.relative_to(workspace).as_posix())
    return _sha256_concat_files(paths)


def _replay_forced_run_id(*, replay_of: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")
    suffix = sha256(f"{replay_of}:{ts}".encode("utf-8")).hexdigest()[:8]
    return f"replay-{ts}-{suffix}"


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--envelope", help="Path to a request envelope JSON.")
    mode.add_argument("--resume", help="Path to an evidence/<run_id> directory to resume.")
    mode.add_argument("--replay", help="Path to an evidence/<run_id> directory to replay.")
    ap.add_argument("--approve", type=budget_runtime.parse_bool, default=False)
    ap.add_argument("--force-new-run", type=budget_runtime.parse_bool, default=False)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="evidence")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    out_dir = Path(args.out)
    out_dir = (workspace / out_dir).resolve() if not out_dir.is_absolute() else out_dir.resolve()
    try:
        out_dir.relative_to(workspace)
    except ValueError:
        raise SystemExit("--out must be within --workspace for safety.")

    if args.resume:
        resume_in = Path(args.resume)
        resume_dir = (workspace / resume_in).resolve() if not resume_in.is_absolute() else resume_in.resolve()
        try:
            resume_dir.relative_to(workspace)
        except ValueError:
            _print_error(
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
            _print_error(
                "INVALID_RESUME_EVIDENCE",
                "Failed to load request.json from evidence directory.",
                details={"request_path": str(request_path), "error": str(e)},
            )
            raise SystemExit(2)

        try:
            summary_existing = load_json(summary_path)
        except Exception as e:
            _print_error(
                "INVALID_RESUME_EVIDENCE",
                "Failed to load summary.json from evidence directory.",
                details={"summary_path": str(summary_path), "error": str(e)},
            )
            raise SystemExit(2)

        if not isinstance(summary_existing, dict):
            _print_error(
                "INVALID_RESUME_EVIDENCE",
                "Evidence summary.json must be a JSON object.",
                details={"summary_path": str(summary_path)},
            )
            raise SystemExit(2)

        run_id = summary_existing.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            run_id = resume_dir.name

        if summary_existing.get("result_state") != "SUSPENDED":
            _print_error(
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
            _print_error(
                "INVALID_RESUME_EVIDENCE",
                "Missing or invalid MOD_A output in evidence; cannot resume MOD_B.",
                details={"mod_a_output_path": str(mod_a_output_path), "error": str(e)},
            )
            raise SystemExit(2)

        if not isinstance(mod_a_output, dict):
            _print_error(
                "INVALID_RESUME_EVIDENCE",
                "MOD_A output.json must be a JSON object.",
                details={"mod_a_output_path": str(mod_a_output_path)},
            )
            raise SystemExit(2)

        governor = runner_config.load_governor(workspace)
        governor_mode_used = governor.get("global_mode", "normal")
        quarantine = governor.get("quarantine") if isinstance(governor.get("quarantine"), dict) else {}
        quarantined_intents = set(
            x for x in quarantine.get("intents", []) if isinstance(x, str) and x
        )
        quarantined_workflows = set(
            x for x in quarantine.get("workflows", []) if isinstance(x, str) and x
        )
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
                _print_error(
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
                _print_error(
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
                _print_error(
                    "GOVERNOR_BLOCK",
                    "Governor blocked resume.",
                    details={"policy_violation_code": e.error_code, "dlq_file": dlq_path.name},
                )
                raise SystemExit(1)

            evidence = EvidenceWriter(out_dir=resume_dir.parent, run_id=resume_dir.name)
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
                    _print_error(
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
                _print_error("RESUME_FAILED", "Resume failed.", details={"run_id": run_id, "error": str(e)})
                raise SystemExit(1)
        finally:
            if lock_acquired:
                runner_config.release_governor_lock(lock_path)

    replay_of: str | None = None
    replay_provenance: dict[str, Any] | None = None
    force_new_run = bool(args.force_new_run)
    replay_force_new_run = force_new_run if args.replay else False
    replay_warnings: list[str] = []

    if args.replay:
        replay_in = Path(args.replay)
        replay_dir = (workspace / replay_in).resolve() if not replay_in.is_absolute() else replay_in.resolve()
        try:
            replay_dir.relative_to(workspace)
        except ValueError:
            _print_error(
                "INVALID_REPLAY_PATH",
                "--replay must be within --workspace for safety.",
                details={"replay_dir": str(replay_dir), "workspace": str(workspace)},
            )
            raise SystemExit(2)

        replay_of = replay_dir.name
        envelope_path = replay_dir / "request.json"
        if not envelope_path.exists():
            _print_error(
                "INVALID_REPLAY_EVIDENCE",
                "Replay evidence must contain request.json.",
                details={"request_path": str(envelope_path)},
            )
            raise SystemExit(2)

        try:
            envelope = load_json(envelope_path)
        except Exception as e:
            _print_error(
                "INVALID_REPLAY_EVIDENCE",
                "Failed to load request.json from replay evidence directory.",
                details={"request_path": str(envelope_path), "error": str(e)},
            )
            raise SystemExit(2)

        prov_path = replay_dir / "provenance.v1.json"
        if prov_path.exists():
            try:
                prov = load_json(prov_path)
                if isinstance(prov, dict):
                    replay_provenance = prov
            except Exception:
                replay_provenance = None
    else:
        envelope_path_in = Path(args.envelope)
        envelope_path = (
            (workspace / envelope_path_in).resolve()
            if not envelope_path_in.is_absolute()
            else envelope_path_in.resolve()
        )

        try:
            envelope = load_json(envelope_path)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="ENVELOPE_VALIDATE",
                error_code="SCHEMA_INVALID",
                message="Failed to parse envelope JSON.",
                envelope={},
            )
            _print_error(
                "INVALID_ENVELOPE_JSON",
                "Failed to parse envelope JSON.",
                details={"envelope_path": str(envelope_path), "error": str(e)},
            )
            raise SystemExit(2)

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
            _print_error(
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
        _print_error("INVALID_ENVELOPE_SCHEMA", "Envelope failed schema validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope schema validation could not be performed.",
            envelope=envelope,
        )
        _print_error(
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
        _print_error(
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
            _print_error(
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
            _print_error(
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
            _print_error("INVALID_STRATEGY_TABLE", "Strategy table failed intent-registry validation.", details=details)
            raise SystemExit(2)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="STRATEGY_VALIDATE",
                error_code="STRATEGY_INVALID",
                message="Strategy table validation could not be performed.",
                envelope=envelope,
            )
            _print_error(
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
            _print_error(
                "INVALID_STRATEGY_TABLE",
                "Strategy table is invalid.",
                details={"strategy_table_path": str(strategy_path), "error": str(e)},
            )
            raise SystemExit(2)

        intent = envelope.get("intent")
        if not isinstance(intent, str) or not intent:
            _print_error(
                "INVALID_ENVELOPE",
                "Envelope missing intent.",
                details={"envelope_path": str(envelope_path)},
            )
            raise SystemExit(2)

        risk_score = _safe_float(envelope.get("risk_score", 0.0), default=0.0)
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
            _print_error(
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
            _print_error(
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
            _print_error("INVALID_WORKFLOW", "Workflow failed internal validation.", details=details)
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
            _print_error(
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
                current_policies_hash = _hash_json_dir(workspace, "policies")
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
                run_id = _replay_forced_run_id(replay_of=replay_of or request_id or "unknown")
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
                _replay_forced_run_id(replay_of=replay_of or request_id or "unknown")
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

        provider = DeterministicStubProvider()
        provider_used_default = "stub"
        model_used_default = None

        try:
            exec_started_at = dlq.iso_utc_now()
            exec_t0 = time.perf_counter()
            exec_summary = execute_workflow(
                envelope=envelope,
                workflow=workflow,
                provider=provider,
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


if __name__ == "__main__":
    main()
