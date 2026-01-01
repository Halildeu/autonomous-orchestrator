import argparse
import json
import sys
from pathlib import Path
from hashlib import sha256

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.budget import estimate_tokens  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_approval_threshold(decision_policy_path: Path, *, default: float = 0.7) -> float:
    if not decision_policy_path.exists():
        return default
    try:
        raw = load_json(decision_policy_path)
    except Exception:
        return default

    v = raw.get("approval_risk_threshold", default)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f < 0 or f > 1:
        return default
    return f


def _safe_str(value):
    if isinstance(value, str) and value:
        return value
    return None


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relpath(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path)


def _is_invalid_fixture_filename(path: Path) -> bool:
    return path.name.endswith("_invalid.json")


def _load_envelope_validator(schema_path: Path) -> Draft202012Validator:
    if not schema_path.exists():
        raise SystemExit(f"Missing envelope schema: {schema_path}")
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _envelope_schema_errors(validator: Draft202012Validator, instance) -> list[dict[str, str]]:
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [{"path": e.json_path or "$", "message": e.message} for e in errors]


def _safe_tenant_and_request_id(env: dict) -> tuple[str | None, str | None]:
    tenant_id = _safe_str(env.get("tenant_id")) if isinstance(env, dict) else None
    request_id = _safe_str(env.get("request_id")) if isinstance(env, dict) else None
    return tenant_id, request_id


def _compute_idempotency_key_hash(
    env: dict,
    *,
    workflow_id: str | None,
) -> str | None:
    if not isinstance(env, dict):
        return None

    existing = env.get("idempotency_key_hash")
    if isinstance(existing, str) and existing:
        return existing

    tenant_id, _ = _safe_tenant_and_request_id(env)
    idempotency_key = env.get("idempotency_key")
    if not (isinstance(tenant_id, str) and tenant_id and isinstance(idempotency_key, str) and idempotency_key):
        return None

    key_plain = f"{tenant_id}:{idempotency_key}:{workflow_id}" if workflow_id else f"{tenant_id}:{idempotency_key}"
    return sha256(key_plain.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixtures", default="fixtures/envelopes")
    ap.add_argument("--evidence", default="evidence")
    ap.add_argument("--source", choices=["fixtures", "evidence", "both"], default="fixtures")
    args = ap.parse_args()

    repo_root = Path.cwd()

    st_path = Path("orchestrator/strategy_table.v1.json")
    if not st_path.exists():
        raise SystemExit("Missing orchestrator/strategy_table.v1.json")

    decision_policy_path = Path("orchestrator/decision_policy.v1.json")
    threshold_used = read_approval_threshold(decision_policy_path, default=0.7)

    envelope_schema_path = Path("schemas/request-envelope.schema.json")
    envelope_validator = _load_envelope_validator(envelope_schema_path)

    st = load_json(st_path)
    routes = st.get("routes", [])
    if not isinstance(routes, list):
        raise SystemExit("Invalid strategy table: routes must be a list.")

    mapping: dict[str, str] = {}
    for idx, row in enumerate(routes):
        if not isinstance(row, dict):
            raise SystemExit(f"Invalid strategy table: routes[{idx}] must be an object.")
        intent = row.get("intent")
        workflow_id = row.get("workflow_id")
        if not isinstance(intent, str) or not intent:
            raise SystemExit(f"Invalid strategy table: routes[{idx}].intent must be a non-empty string.")
        if not isinstance(workflow_id, str) or not workflow_id:
            raise SystemExit(f"Invalid strategy table: routes[{idx}].workflow_id must be a non-empty string.")
        mapping[intent] = workflow_id

    fixture_paths: list[Path] = []
    if args.source in {"fixtures", "both"}:
        fixtures_dir = Path(args.fixtures)
        if fixtures_dir.exists():
            fixture_paths = sorted(fixtures_dir.glob("*.json"), key=lambda p: p.name)

    evidence_paths: list[Path] = []
    if args.source in {"evidence", "both"}:
        evidence_dir = Path(args.evidence)
        if evidence_dir.exists():
            evidence_paths = sorted(
                [p for p in evidence_dir.rglob("request.json") if p.is_file()],
                key=lambda p: _relpath(p, repo_root),
            )

    if args.source == "fixtures" and not fixture_paths:
        raise SystemExit("No fixture envelopes found.")
    if args.source == "evidence" and not evidence_paths:
        raise SystemExit("No evidence request.json files found.")
    if args.source == "both" and not fixture_paths and not evidence_paths:
        raise SystemExit("No inputs found from fixtures or evidence.")

    categories = ["allow", "suspend", "block_unknown_intent", "invalid_envelope"]
    counts = {k: 0 for k in categories}
    examples: dict[str, list[dict]] = {k: [] for k in categories}

    budget_warn_count = 0
    budget_warn_examples: list[dict] = []

    # Quota warnings (additive): simulate runs/day starting from 0 in deterministic input order.
    quota_policy_path = Path("policies/policy_quota.v1.json")
    quota_default_runs = 2
    quota_overrides_runs: dict[str, int] = {}
    if quota_policy_path.exists():
        try:
            qraw = load_json(quota_policy_path)
            if isinstance(qraw, dict):
                dcfg = qraw.get("default") if isinstance(qraw.get("default"), dict) else {}
                try:
                    quota_default_runs = int(dcfg.get("max_runs_per_day", quota_default_runs))
                except Exception:
                    quota_default_runs = 2
                if quota_default_runs < 1:
                    quota_default_runs = 1

                ocfg = qraw.get("overrides") if isinstance(qraw.get("overrides"), dict) else {}
                for tenant_id, cfg in ocfg.items():
                    if not isinstance(tenant_id, str) or not tenant_id:
                        continue
                    if not isinstance(cfg, dict):
                        continue
                    try:
                        n = int(cfg.get("max_runs_per_day", quota_default_runs))
                    except Exception:
                        n = quota_default_runs
                    if n < 1:
                        n = 1
                    quota_overrides_runs[tenant_id] = n
        except Exception:
            quota_default_runs = 2
            quota_overrides_runs = {}

    def _quota_max_runs_for(tenant_id: str | None) -> int:
        tid = tenant_id or "unknown"
        return int(quota_overrides_runs.get(tid, quota_default_runs))

    quota_warn_count = 0
    quota_warn_examples: list[dict] = []
    quota_sim_runs_used: dict[str, int] = {}

    inputs: list[dict] = []
    for p in fixture_paths:
        inputs.append({"source": "fixtures", "path": p, "sort_key": (0, p.name)})
    for p in evidence_paths:
        inputs.append({"source": "evidence", "path": p, "sort_key": (1, _relpath(p, repo_root))})

    inputs = sorted(inputs, key=lambda x: x["sort_key"])

    # Deduplicate deterministically to avoid double-counting when using --source both.
    seen_keys: set[tuple[str, str, str]] = set()
    unique_inputs: list[dict] = []
    for item in inputs:
        path = item["path"]
        src = item["source"]
        file_rel = _relpath(path, repo_root)

        env = None
        json_error = None
        try:
            env = load_json(path)
        except Exception as e:
            json_error = str(e)

        item["file"] = file_rel
        item["env"] = env
        item["json_error"] = json_error

        if isinstance(env, dict):
            intent = env.get("intent") if isinstance(env.get("intent"), str) else None
            workflow_id = mapping.get(intent) if isinstance(intent, str) else None
            id_hash = _compute_idempotency_key_hash(env, workflow_id=workflow_id) or ""
            tenant_id, request_id = _safe_tenant_and_request_id(env)
            if tenant_id and request_id:
                dkey = (tenant_id, request_id, id_hash)
                if dkey in seen_keys:
                    continue
                seen_keys.add(dkey)

        unique_inputs.append(item)

    for item in unique_inputs:
        src = item["source"]
        fixture_path = item["path"]
        file_rel = item["file"]
        env = item["env"]
        json_error = item["json_error"]

        request_id = _safe_str(env.get("request_id")) if isinstance(env, dict) else None
        intent = _safe_str(env.get("intent")) if isinstance(env, dict) else None
        risk_score_raw = env.get("risk_score") if isinstance(env, dict) else None
        risk_score = _safe_float(risk_score_raw)

        invalid_reason = None
        if json_error is not None:
            invalid_reason = "JSON_INVALID"
        else:
            schema_errors = _envelope_schema_errors(envelope_validator, env)
            if schema_errors:
                invalid_reason = "SCHEMA_INVALID"
            elif src == "fixtures" and _is_invalid_fixture_filename(fixture_path):
                invalid_reason = "FILENAME_MARKED_INVALID"

        if invalid_reason is not None:
            category = "invalid_envelope"
            counts[category] += 1
            if len(examples[category]) < 5:
                examples[category].append(
                    {
                        "file": file_rel,
                        "request_id": request_id,
                        "intent": intent,
                        "risk_score": risk_score_raw,
                        "reason": invalid_reason,
                    }
                )
            continue

        # Quota warnings: assume each valid fixture would count as a run.
        tenant_id = _safe_str(env.get("tenant_id")) if isinstance(env, dict) else None
        tid = tenant_id or "unknown"
        max_runs_for_tenant = _quota_max_runs_for(tenant_id)
        current_runs = int(quota_sim_runs_used.get(tid, 0))
        would_runs = current_runs + 1
        if would_runs > int(max_runs_for_tenant):
            quota_warn_count += 1
            if len(quota_warn_examples) < 5:
                quota_warn_examples.append(
                    {
                        "file": file_rel,
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "intent": intent,
                        "risk_score": risk_score,
                        "max_runs_per_day": max_runs_for_tenant,
                        "sim_runs_used_before": current_runs,
                        "reason": "MAX_RUNS_PER_DAY_EXCEEDED",
                    }
                )
        quota_sim_runs_used[tid] = would_runs

        # Budget warnings (additive): lightweight estimate based on input markdown only.
        try:
            budget_raw = env.get("budget") if isinstance(env, dict) else None
            max_tokens_raw = budget_raw.get("max_tokens") if isinstance(budget_raw, dict) else None
            max_tokens = int(max_tokens_raw) if max_tokens_raw is not None else None
        except Exception:
            max_tokens = None

        if isinstance(max_tokens, int) and max_tokens > 0:
            ctx = env.get("context") if isinstance(env.get("context"), dict) else {}
            input_path_raw = ctx.get("input_path")
            input_rel = input_path_raw.strip() if isinstance(input_path_raw, str) and input_path_raw.strip() else "fixtures/sample.md"
            try:
                input_abs = (repo_root / input_rel).resolve()
                input_abs.relative_to(repo_root.resolve())
                text = input_abs.read_text(encoding="utf-8")
                est_min_tokens = estimate_tokens(text)
                if est_min_tokens > max_tokens:
                    budget_warn_count += 1
                    if len(budget_warn_examples) < 5:
                        budget_warn_examples.append(
                            {
                                "file": file_rel,
                                "request_id": request_id,
                                "intent": intent,
                                "risk_score": risk_score,
                                "max_tokens": max_tokens,
                                "est_min_tokens": est_min_tokens,
                                "reason": "MAX_TOKENS_LT_EST_MIN_TOKENS",
                            }
                        )
            except Exception:
                pass

        if not (intent and intent in mapping):
            category = "block_unknown_intent"
            counts[category] += 1
            if len(examples[category]) < 5:
                examples[category].append(
                    {
                        "file": file_rel,
                        "request_id": request_id,
                        "intent": intent,
                        "risk_score": risk_score,
                        "reason": "UNKNOWN_INTENT",
                    }
                )
            continue

        if risk_score is not None and risk_score >= threshold_used:
            category = "suspend"
            counts[category] += 1
            if len(examples[category]) < 5:
                examples[category].append(
                    {
                        "file": file_rel,
                        "request_id": request_id,
                        "intent": intent,
                        "risk_score": risk_score,
                        "reason": "RISK_GE_THRESHOLD",
                    }
                )
            continue

        category = "allow"
        counts[category] += 1
        if len(examples[category]) < 5:
            examples[category].append(
                {
                    "file": file_rel,
                    "request_id": request_id,
                    "intent": intent,
                    "risk_score": risk_score,
                    "reason": "ALLOW",
                }
            )

    report = {
        "fixtures_total": len(fixture_paths),
        "source": args.source,
        "total_inputs": len(unique_inputs),
        "inputs_breakdown": {"fixtures": len(fixture_paths), "evidence": len(evidence_paths)},
        "threshold_used": threshold_used,
        "counts": counts,
        "examples": examples,
        "quota_warnings": {
            "would_exceed_runs_per_day": {
                "count": quota_warn_count,
                "examples": quota_warn_examples,
                "note": "Simulated in deterministic input order, starting at 0 runs/day per tenant.",
            }
        },
        "budget_warnings": {
            "would_fail_budget_tokens": {
                "count": budget_warn_count,
                "examples": budget_warn_examples,
                "note": "Lightweight estimate: compares budget.max_tokens to est_tokens(input_markdown) only.",
            }
        },
    }

    Path(args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
