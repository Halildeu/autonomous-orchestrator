from __future__ import annotations

import argparse
import json
import re
import secrets
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.evidence.writer import EvidenceWriter
from src.orchestrator.route import load_strategy_table, route_intent
from src.orchestrator.workflow_exec import execute_mod_b_only, execute_workflow, read_approval_threshold
from src.providers.openai_provider import get_provider
from src.utils.jsonio import load_json, to_canonical_json


def _timestamp_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{secrets.token_hex(3)}"


def _deterministic_run_id(
    *,
    tenant_id: str,
    idempotency_key: str,
    workflow_id: str,
    workflow_fingerprint: str,
) -> str:
    raw = f"{tenant_id}:{idempotency_key}:{workflow_id}:{workflow_fingerprint}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def _schema_errors(instance: Any, schema_path: Path) -> list[dict[str, str]]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [{"path": e.json_path or "$", "message": e.message} for e in errors]


def _print_error(kind: str, message: str, *, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"status": "ERROR", "error_type": kind, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _validate_envelope(envelope: Any, *, schema_path: Path, envelope_path: Path) -> None:
    if not schema_path.exists():
        raise RuntimeError(f"Missing envelope schema: {schema_path}")

    if not isinstance(envelope, dict):
        raise RuntimeError("Envelope must be a JSON object.")

    errors = _schema_errors(envelope, schema_path)
    if errors:
        raise ValueError(
            json.dumps(
                {
                    "envelope_path": str(envelope_path),
                    "schema_path": str(schema_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def _validate_strategy_table_intents(strategy_path: Path, *, intent_registry_schema_path: Path) -> None:
    if not intent_registry_schema_path.exists():
        return

    raw = load_json(strategy_path)
    derived = {"version": raw.get("version"), "intents": raw.get("routes", [])}
    errors = _schema_errors(derived, intent_registry_schema_path)
    if errors:
        raise ValueError(
            json.dumps(
                {
                    "strategy_table_path": str(strategy_path),
                    "schema_path": str(intent_registry_schema_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def _validate_workflow(workflow: Any, *, workflow_path: Path) -> None:
    errors: list[dict[str, str]] = []

    if not isinstance(workflow, dict):
        errors.append({"path": "$", "message": "Workflow must be a JSON object."})
    else:
        if not isinstance(workflow.get("version"), str) or not workflow.get("version"):
            errors.append({"path": "$.version", "message": "Workflow must include non-empty version."})
        if not isinstance(workflow.get("workflow_id"), str) or not workflow.get("workflow_id"):
            errors.append({"path": "$.workflow_id", "message": "Workflow must include non-empty workflow_id."})

        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append({"path": "$.steps", "message": "Workflow must include non-empty steps list."})
        else:
            seen_ids: set[str] = set()
            for idx, step in enumerate(steps):
                pfx = f"$.steps[{idx}]"
                if not isinstance(step, dict):
                    errors.append({"path": pfx, "message": "Step must be an object."})
                    continue

                node_id = step.get("id")
                node_type = step.get("type")

                if not isinstance(node_id, str) or not node_id:
                    errors.append({"path": f"{pfx}.id", "message": "Step.id must be a non-empty string."})
                else:
                    if not re.match(r"^[A-Z][A-Z0-9_]{2,64}$", node_id):
                        errors.append(
                            {
                                "path": f"{pfx}.id",
                                "message": "Step.id must match ^[A-Z][A-Z0-9_]{2,64}$ (UPPER_SNAKE_CASE).",
                            }
                        )
                    if node_id in seen_ids:
                        errors.append({"path": f"{pfx}.id", "message": f"Duplicate step id: {node_id}"})
                    seen_ids.add(node_id)

                if not isinstance(node_type, str) or not node_type:
                    errors.append({"path": f"{pfx}.type", "message": "Step.type must be a non-empty string."})
                elif node_type == "module":
                    module_id = step.get("module_id")
                    if not isinstance(module_id, str) or not module_id:
                        errors.append(
                            {"path": f"{pfx}.module_id", "message": "Module step requires non-empty module_id."}
                        )
                    elif module_id not in {"MOD_A", "MOD_B"}:
                        errors.append({"path": f"{pfx}.module_id", "message": f"Unsupported module_id: {module_id}"})
                elif node_type == "approval":
                    pass
                else:
                    errors.append({"path": f"{pfx}.type", "message": f"Unsupported step.type: {node_type}"})

    if errors:
        raise ValueError(
            json.dumps(
                {
                    "workflow_path": str(workflow_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def _load_workflow_by_id(workspace: Path, workflow_id: str) -> tuple[Path, dict[str, Any]]:
    workflows_dir = workspace / "workflows"
    if not workflows_dir.exists():
        raise RuntimeError("Missing workflows/ directory.")

    matches: list[tuple[Path, dict[str, Any]]] = []
    for wf_path in sorted(workflows_dir.glob("*.json")):
        try:
            wf = load_json(wf_path)
        except Exception:
            continue
        if wf.get("workflow_id") == workflow_id:
            matches.append((wf_path, wf))

    if not matches:
        raise RuntimeError(f"Workflow not found for workflow_id={workflow_id}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple workflow files match workflow_id={workflow_id}: {[str(p) for p, _ in matches]}")
    return matches[0]


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dlq_ts_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _sanitize_filename_component(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    s = "".join(keep).strip("_")
    if not s:
        return "unknown"
    return s[:80]


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dlq_min_envelope(envelope: Any, *, workflow_id: str | None = None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {
            "request_id": None,
            "tenant_id": None,
            "intent": None,
            "risk_score": None,
            "dry_run": None,
            "side_effect_policy": None,
            "idempotency_key_hash": None,
        }

    request_id = envelope.get("request_id") if isinstance(envelope.get("request_id"), str) else None
    tenant_id = envelope.get("tenant_id") if isinstance(envelope.get("tenant_id"), str) else None
    intent = envelope.get("intent") if isinstance(envelope.get("intent"), str) else None
    risk_score_raw = envelope.get("risk_score")
    try:
        risk_score = float(risk_score_raw)
    except (TypeError, ValueError):
        risk_score = None

    dry_run_value = envelope.get("dry_run")
    dry_run = dry_run_value if isinstance(dry_run_value, bool) else None

    side_effect_policy = (
        envelope.get("side_effect_policy") if isinstance(envelope.get("side_effect_policy"), str) else None
    )

    idempotency_key_hash = None
    idempotency_key = envelope.get("idempotency_key")
    if tenant_id and isinstance(idempotency_key, str) and idempotency_key:
        if workflow_id:
            key_plain = f"{tenant_id}:{idempotency_key}:{workflow_id}"
        else:
            key_plain = f"{tenant_id}:{idempotency_key}"
        idempotency_key_hash = sha256(key_plain.encode("utf-8")).hexdigest()

    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "intent": intent,
        "risk_score": risk_score,
        "dry_run": dry_run,
        "side_effect_policy": side_effect_policy,
        "idempotency_key_hash": idempotency_key_hash,
    }


def _write_dlq_record(
    *,
    workspace: Path,
    stage: str,
    error_code: str,
    message: str,
    envelope: Any,
    workflow_id: str | None = None,
) -> Path:
    dlq_dir = workspace / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)

    minimal = _dlq_min_envelope(envelope, workflow_id=workflow_id)
    rid = minimal.get("request_id") or "unknown"
    fname = f"{_dlq_ts_filename()}_{_sanitize_filename_component(str(rid))}.json"
    path = dlq_dir / fname

    record = {
        "stage": stage,
        "error_code": error_code,
        "message": message,
        "envelope": minimal,
        "ts": _iso_utc_now(),
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _workflow_fingerprint(workflow: dict[str, Any], workflow_path: Path) -> str:
    version = workflow.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()

    try:
        raw = workflow_path.read_bytes()
    except Exception:
        raw = to_canonical_json(workflow).encode("utf-8")
    return sha256(raw).hexdigest()


def _load_idempotency_store(store_path: Path) -> tuple[dict[str, str], bool]:
    if not store_path.exists():
        return ({}, False)
    try:
        raw = load_json(store_path)
    except Exception:
        return ({}, False)

    if isinstance(raw, dict) and isinstance(raw.get("mappings"), dict):
        src = raw["mappings"]
    elif isinstance(raw, dict):
        src = {k: v for k, v in raw.items() if k != "version"}
    else:
        return ({}, False)

    loaded = {str(k): str(v) for k, v in src.items()}

    migrated = False
    migrated_map: dict[str, str] = {}
    for k, v in loaded.items():
        if ":" in k:
            migrated = True
            migrated_map[sha256(k.encode("utf-8")).hexdigest()[:24]] = v
        else:
            migrated_map[k] = v

    return (migrated_map, migrated)


def _save_idempotency_store(store_path: Path, mappings: dict[str, str]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "v1", "mappings": dict(sorted(mappings.items()))}
    store_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_result_state(summary_path: Path) -> str | None:
    if not summary_path.exists():
        return None
    try:
        summary = load_json(summary_path)
    except Exception:
        return None
    if not isinstance(summary, dict):
        return None
    rs = summary.get("result_state")
    if isinstance(rs, str) and rs:
        return rs
    st = summary.get("status")
    if isinstance(st, str) and st:
        return st
    return None


def _parse_bool(text: str) -> bool:
    v = text.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean: true/false")


def _duration_ms_from_started(started_at: Any, finished_at: str, *, fallback: Any = None) -> int:
    try:
        if isinstance(started_at, str) and started_at:
            s = datetime.fromisoformat(started_at)
            f = datetime.fromisoformat(finished_at)
            return int((f - s).total_seconds() * 1000)
    except Exception:
        pass

    if isinstance(fallback, int):
        return fallback
    try:
        return int(fallback)
    except Exception:
        return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--envelope", help="Path to a request envelope JSON.")
    mode.add_argument("--resume", help="Path to an evidence/<run_id> directory to resume.")
    ap.add_argument("--approve", type=_parse_bool, default=False)
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

        evidence = EvidenceWriter(out_dir=resume_dir.parent, run_id=resume_dir.name)
        resumed_at = _iso_utc_now()

        try:
            res = execute_mod_b_only(
                envelope=envelope,
                mod_a_output=mod_a_output,
                workspace=workspace,
                evidence=evidence,
                node_id="MOD_B",
            )
            finished_at = _iso_utc_now()

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
            updated["duration_ms"] = _duration_ms_from_started(
                updated.get("started_at"), finished_at, fallback=updated.get("duration_ms")
            )
            updated["nodes"] = nodes

            evidence.write_summary(updated)
            evidence.write_resume_log(f"{resumed_at} RESUME approve=true\n")

            print(json.dumps(updated, indent=2, ensure_ascii=False))
            if updated["result_state"] != "COMPLETED":
                raise SystemExit(1)
            return
        except SystemExit:
            raise
        except Exception as e:
            finished_at = _iso_utc_now()
            updated = dict(summary_existing)
            updated["resumed"] = True
            updated["resumed_at"] = resumed_at
            updated["result_state"] = "FAILED"
            updated["status"] = "FAILED"
            updated["finished_at"] = finished_at
            updated["duration_ms"] = _duration_ms_from_started(
                updated.get("started_at"), finished_at, fallback=updated.get("duration_ms")
            )
            updated["resume_error"] = str(e)
            evidence.write_summary(updated)
            evidence.write_resume_log(f"{resumed_at} RESUME_FAILED {str(e)}\n")
            _print_error("RESUME_FAILED", "Resume failed.", details={"run_id": run_id, "error": str(e)})
            raise SystemExit(1)

    envelope_path_in = Path(args.envelope)
    envelope_path = (
        (workspace / envelope_path_in).resolve()
        if not envelope_path_in.is_absolute()
        else envelope_path_in.resolve()
    )

    try:
        envelope = load_json(envelope_path)
    except Exception as e:
        _write_dlq_record(
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
        _validate_envelope(envelope, schema_path=envelope_schema_path, envelope_path=envelope_path)
    except ValueError as e:
        _write_dlq_record(
            workspace=workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope failed schema validation.",
            envelope=envelope,
        )
        details = json.loads(str(e))
        _print_error("INVALID_ENVELOPE_SCHEMA", "Envelope failed schema validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        _write_dlq_record(
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

    started_at = _iso_utc_now()
    t0 = time.perf_counter()

    strategy_path = workspace / "orchestrator" / "strategy_table.v1.json"
    intent_registry_schema_path = workspace / "schemas" / "intent-registry.schema.json"
    try:
        _validate_strategy_table_intents(strategy_path, intent_registry_schema_path=intent_registry_schema_path)
    except ValueError as e:
        _write_dlq_record(
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
        _write_dlq_record(
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
        _write_dlq_record(
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
    if not workflow_id:
        _write_dlq_record(
            workspace=workspace,
            stage="ROUTE",
            error_code="UNKNOWN_INTENT",
            message="Unknown intent; no route found in strategy table.",
            envelope=envelope,
        )
        run_id = _timestamp_run_id()

        evidence = EvidenceWriter(out_dir=out_dir, run_id=run_id)
        evidence.write_request(envelope)
        finished_at = _iso_utc_now()
        duration_ms = int((time.perf_counter() - t0) * 1000)
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
            "workflow_fingerprint": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": None,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
        }
        evidence.write_summary(summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise SystemExit(2)

    try:
        workflow_path, workflow = _load_workflow_by_id(workspace, workflow_id)
    except Exception as e:
        _write_dlq_record(
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
        _validate_workflow(workflow, workflow_path=workflow_path)
    except ValueError as e:
        _write_dlq_record(
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
        _write_dlq_record(
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

    workflow_fingerprint = _workflow_fingerprint(workflow, workflow_path)

    decision_policy_path = workspace / "orchestrator" / "decision_policy.v1.json"
    approval_threshold_used = read_approval_threshold(decision_policy_path, default=0.7)

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
        store_key_id = idempotency_key_hash[:24]
        run_id = _deterministic_run_id(
            tenant_id=tenant_id_raw,
            idempotency_key=idempotency_key,
            workflow_id=workflow_id,
            workflow_fingerprint=workflow_fingerprint,
        )
    else:
        run_id = _timestamp_run_id()

    store_path = workspace / ".cache" / "idempotency_store.v1.json"
    mappings, migrated = _load_idempotency_store(store_path)
    changed = migrated
    if store_key_id:
        if mappings.get(store_key_id) != run_id:
            mappings[store_key_id] = run_id
            changed = True
        if changed or not store_path.exists():
            _save_idempotency_store(store_path, mappings)

        summary_path = out_dir / run_id / "summary.json"
        if _read_result_state(summary_path) == "COMPLETED":
            print(
                json.dumps(
                    {
                        "status": "IDEMPOTENT_HIT",
                        "message": "IDEMPOTENT_HIT",
                        "run_id": run_id,
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "workflow_id": workflow_id,
                        "workflow_fingerprint": workflow_fingerprint,
                        "approval_threshold_used": approval_threshold_used,
                        "idempotency_key_hash": idempotency_key_hash,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return

    evidence = EvidenceWriter(out_dir=out_dir, run_id=run_id)
    evidence.write_request(envelope)

    provider = get_provider()

    provider_used_default = "stub"
    model_used_default = None
    if hasattr(provider, "_model"):
        provider_used_default = "openai"
        model_used_default = getattr(provider, "_model")

    try:
        exec_started_at = _iso_utc_now()
        exec_t0 = time.perf_counter()
        exec_summary = execute_workflow(
            envelope=envelope,
            workflow=workflow,
            provider=provider,
            workspace=workspace,
            evidence=evidence,
            approval_threshold=approval_threshold_used,
        )
        finished_at = _iso_utc_now()
        duration_ms = int((time.perf_counter() - exec_t0) * 1000)

        provider_used = exec_summary.get("provider_used") or provider_used_default
        model_used = exec_summary.get("model_used") if exec_summary.get("model_used") is not None else model_used_default

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
            "workflow_fingerprint": workflow_fingerprint,
            "started_at": exec_started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": idempotency_key_hash,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "nodes": exec_summary.get("nodes", []),
        }
        if "token_usage" in exec_summary:
            summary["token_usage"] = exec_summary.get("token_usage")
    except Exception as e:
        finished_at = _iso_utc_now()
        duration_ms = int((time.perf_counter() - t0) * 1000)
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
            "provider_used": provider_used_default,
            "model_used": model_used_default,
            "workflow_fingerprint": workflow_fingerprint,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "idempotency_key_hash": idempotency_key_hash,
            "idempotency_key_hash_source": 'sha256("tenant_id:idempotency_key:workflow_id")',
            "error": str(e),
        }

    evidence.write_summary(summary)
    if summary.get("result_state") == "SUSPENDED":
        resume_path = evidence.run_dir
        try:
            resume_path = evidence.run_dir.resolve().relative_to(workspace.resolve())
        except ValueError:
            resume_path = evidence.run_dir

        evidence.write_suspend(
            {
                "run_id": run_id,
                "reason": "APPROVAL_REQUIRED",
                "risk_score": risk_score,
                "threshold_used": approval_threshold_used,
                "next_action_hint": f"Resume with --resume {resume_path} --approve true",
            }
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if summary.get("status") == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
