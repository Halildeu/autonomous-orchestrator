import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.budget import estimate_tokens  # noqa: E402


@dataclass(frozen=True)
class SimConfig:
    threshold_used: float
    mapping: dict[str, str]
    quota_default_runs: int
    quota_overrides_runs: dict[str, int]
    policies_hash: str


def _load_json_bytes(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"))


def _load_json_path(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_ref_exists(ref: str, *, cwd: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def _git_show_bytes(ref: str, repo_path: str, *, cwd: Path) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{repo_path}"],
        cwd=cwd,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _git_list_paths(ref: str, prefix: str, *, cwd: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, prefix],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _safe_str(value) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _safe_float(value) -> float | None:
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
    schema = _load_json_path(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _envelope_schema_errors(validator: Draft202012Validator, instance) -> list[dict[str, str]]:
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [{"path": e.json_path or "$", "message": e.message} for e in errors]


def _read_approval_threshold_from_obj(obj: object, *, default: float = 0.7) -> float:
    if not isinstance(obj, dict):
        return default
    v = obj.get("approval_risk_threshold", default)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f < 0 or f > 1:
        return default
    return f


def _strategy_mapping_from_obj(obj: object) -> dict[str, str]:
    if not isinstance(obj, dict):
        return {}
    routes = obj.get("routes", [])
    if not isinstance(routes, list):
        return {}
    mapping: dict[str, str] = {}
    for row in routes:
        if not isinstance(row, dict):
            continue
        intent = row.get("intent")
        workflow_id = row.get("workflow_id")
        if isinstance(intent, str) and intent and isinstance(workflow_id, str) and workflow_id:
            mapping[intent] = workflow_id
    return mapping


def _sha256_concat_bytes(blobs: list[bytes]) -> str:
    h = sha256()
    for b in blobs:
        h.update(b)
    return h.hexdigest()


def _load_quota_policy_from_obj(obj: object) -> tuple[int, dict[str, int]]:
    quota_default_runs = 2
    quota_overrides_runs: dict[str, int] = {}
    if not isinstance(obj, dict):
        return (quota_default_runs, quota_overrides_runs)

    dcfg = obj.get("default") if isinstance(obj.get("default"), dict) else {}
    try:
        quota_default_runs = int(dcfg.get("max_runs_per_day", quota_default_runs))
    except Exception:
        quota_default_runs = 2
    if quota_default_runs < 1:
        quota_default_runs = 1

    ocfg = obj.get("overrides") if isinstance(obj.get("overrides"), dict) else {}
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

    return (quota_default_runs, quota_overrides_runs)


def _quota_max_runs_for(tenant_id: str | None, *, default_runs: int, overrides: dict[str, int]) -> int:
    tid = tenant_id or "unknown"
    return int(overrides.get(tid, default_runs))


def _load_candidate_config(*, workspace: Path) -> SimConfig:
    strategy_obj = _load_json_path(workspace / "orchestrator" / "strategy_table.v1.json")
    decision_obj = _load_json_path(workspace / "orchestrator" / "decision_policy.v1.json")

    threshold_used = _read_approval_threshold_from_obj(decision_obj, default=0.7)
    mapping = _strategy_mapping_from_obj(strategy_obj)

    policy_paths = sorted((workspace / "policies").glob("*.json"), key=lambda p: p.as_posix())
    policy_blobs = [p.read_bytes() for p in policy_paths if p.is_file()]
    policies_hash = _sha256_concat_bytes(policy_blobs)

    quota_obj: object = {}
    quota_path = workspace / "policies" / "policy_quota.v1.json"
    if quota_path.exists():
        try:
            quota_obj = _load_json_path(quota_path)
        except Exception:
            quota_obj = {}
    quota_default_runs, quota_overrides_runs = _load_quota_policy_from_obj(quota_obj)

    return SimConfig(
        threshold_used=threshold_used,
        mapping=mapping,
        quota_default_runs=quota_default_runs,
        quota_overrides_runs=quota_overrides_runs,
        policies_hash=policies_hash,
    )


def _load_baseline_config(*, workspace: Path, baseline_ref: str) -> SimConfig:
    strategy_raw = _git_show_bytes(baseline_ref, "orchestrator/strategy_table.v1.json", cwd=workspace)
    decision_raw = _git_show_bytes(baseline_ref, "orchestrator/decision_policy.v1.json", cwd=workspace)

    strategy_obj = _load_json_bytes(strategy_raw) if strategy_raw else {}
    decision_obj = _load_json_bytes(decision_raw) if decision_raw else {}

    threshold_used = _read_approval_threshold_from_obj(decision_obj, default=0.7)
    mapping = _strategy_mapping_from_obj(strategy_obj)

    policy_paths = [p for p in _git_list_paths(baseline_ref, "policies", cwd=workspace) if p.endswith(".json")]
    policy_blobs: list[bytes] = []
    for p in sorted(policy_paths):
        b = _git_show_bytes(baseline_ref, p, cwd=workspace)
        if b is not None:
            policy_blobs.append(b)
    policies_hash = _sha256_concat_bytes(policy_blobs)

    quota_obj: object = {}
    quota_raw = _git_show_bytes(baseline_ref, "policies/policy_quota.v1.json", cwd=workspace)
    if quota_raw:
        try:
            quota_obj = _load_json_bytes(quota_raw)
        except Exception:
            quota_obj = {}
    quota_default_runs, quota_overrides_runs = _load_quota_policy_from_obj(quota_obj)

    return SimConfig(
        threshold_used=threshold_used,
        mapping=mapping,
        quota_default_runs=quota_default_runs,
        quota_overrides_runs=quota_overrides_runs,
        policies_hash=policies_hash,
    )


def _classify(
    *,
    validator: Draft202012Validator,
    src: str,
    path: Path,
    file_rel: str,
    env: object,
    json_error: str | None,
    cfg: SimConfig,
    quota_sim_runs_used: dict[str, int],
    workspace: Path,
) -> tuple[str, str, list[str]]:
    request_id = _safe_str(env.get("request_id")) if isinstance(env, dict) else None
    intent = _safe_str(env.get("intent")) if isinstance(env, dict) else None
    risk_score_raw = env.get("risk_score") if isinstance(env, dict) else None
    risk_score = _safe_float(risk_score_raw)

    invalid_reason = None
    if json_error is not None:
        invalid_reason = "JSON_INVALID"
    else:
        schema_errors = _envelope_schema_errors(validator, env)
        if schema_errors:
            invalid_reason = "SCHEMA_INVALID"
        elif src == "fixtures" and _is_invalid_fixture_filename(path):
            invalid_reason = "FILENAME_MARKED_INVALID"

    warnings: list[str] = []

    if invalid_reason is not None:
        return ("invalid_envelope", invalid_reason, warnings)

    # Quota warnings: simulate runs/day starting from 0 in deterministic input order.
    tenant_id = _safe_str(env.get("tenant_id")) if isinstance(env, dict) else None
    tid = tenant_id or "unknown"
    max_runs_for_tenant = _quota_max_runs_for(
        tenant_id, default_runs=cfg.quota_default_runs, overrides=cfg.quota_overrides_runs
    )
    current_runs = int(quota_sim_runs_used.get(tid, 0))
    would_runs = current_runs + 1
    if would_runs > int(max_runs_for_tenant):
        warnings.append("MAX_RUNS_PER_DAY_EXCEEDED")
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
        input_rel = (
            input_path_raw.strip()
            if isinstance(input_path_raw, str) and input_path_raw.strip()
            else "fixtures/sample.md"
        )
        try:
            input_abs = (workspace / input_rel).resolve()
            input_abs.relative_to(workspace.resolve())
            text = input_abs.read_text(encoding="utf-8")
            est_min_tokens = estimate_tokens(text)
            if est_min_tokens > max_tokens:
                warnings.append("MAX_TOKENS_LT_EST_MIN_TOKENS")
        except Exception:
            pass

    if not (intent and intent in cfg.mapping):
        return ("block_unknown_intent", "UNKNOWN_INTENT", warnings)

    if risk_score is not None and risk_score >= cfg.threshold_used:
        return ("suspend", "RISK_GE_THRESHOLD", warnings)

    return ("allow", "ALLOW", warnings)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixtures", default="fixtures/envelopes")
    ap.add_argument("--evidence", default="evidence")
    ap.add_argument("--source", choices=["fixtures", "evidence", "both"], default="fixtures")
    ap.add_argument("--baseline", default="HEAD~1")
    args = ap.parse_args()

    repo_root = Path.cwd().resolve()
    baseline_ref = str(args.baseline)

    out_path = Path(args.out)

    if not _git_ref_exists(baseline_ref, cwd=repo_root):
        report = {
            "baseline_ref": baseline_ref,
            "baseline_available": False,
            "source": args.source,
            "inputs_total": 0,
            "diff_counts": {},
            "examples": {},
            "note": f"Baseline ref not available in git checkout: {baseline_ref}.",
        }
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return

    baseline_cfg = _load_baseline_config(workspace=repo_root, baseline_ref=baseline_ref)
    candidate_cfg = _load_candidate_config(workspace=repo_root)

    envelope_schema_path = repo_root / "schemas" / "request-envelope.schema.json"
    validator = _load_envelope_validator(envelope_schema_path)

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

    inputs: list[dict] = []
    for p in fixture_paths:
        inputs.append({"source": "fixtures", "path": p, "sort_key": (0, p.name)})
    for p in evidence_paths:
        inputs.append({"source": "evidence", "path": p, "sort_key": (1, _relpath(p, repo_root))})
    inputs = sorted(inputs, key=lambda x: x["sort_key"])

    # Deduplicate deterministically (same approach as policy_dry_run.py).
    seen_keys: set[tuple[str, str, str]] = set()
    unique_inputs: list[dict] = []
    for item in inputs:
        path = item["path"]
        src = item["source"]
        file_rel = _relpath(path, repo_root)

        env = None
        json_error = None
        try:
            env = _load_json_path(path)
        except Exception as e:
            json_error = str(e)

        item["file"] = file_rel
        item["env"] = env
        item["json_error"] = json_error

        if isinstance(env, dict):
            tenant_id = _safe_str(env.get("tenant_id"))
            request_id = _safe_str(env.get("request_id"))
            intent = _safe_str(env.get("intent"))

            # Use candidate routing for dedupe key construction (same as policy_dry_run).
            workflow_id = candidate_cfg.mapping.get(intent) if isinstance(intent, str) else None
            id_hash = ""
            if tenant_id and request_id:
                idempotency_key = env.get("idempotency_key")
                if isinstance(idempotency_key, str) and idempotency_key:
                    key_plain = f"{tenant_id}:{idempotency_key}:{workflow_id}" if workflow_id else f"{tenant_id}:{idempotency_key}"
                    id_hash = sha256(key_plain.encode("utf-8")).hexdigest()
                dkey = (tenant_id, request_id, id_hash)
                if dkey in seen_keys:
                    continue
                seen_keys.add(dkey)

        unique_inputs.append(item)

    # Diff counts over stable categories.
    cat_short = {
        "allow": "allow",
        "suspend": "suspend",
        "block_unknown_intent": "block",
        "invalid_envelope": "invalid",
    }
    cats = ["allow", "suspend", "block", "invalid"]
    diff_counts: dict[str, int] = {}
    for a in cats:
        for b in cats:
            if a != b:
                diff_counts[f"{a}_to_{b}"] = 0

    examples: dict[str, list[dict]] = {}

    baseline_quota_sim_runs_used: dict[str, int] = {}
    candidate_quota_sim_runs_used: dict[str, int] = {}

    for item in unique_inputs:
        src = item["source"]
        p: Path = item["path"]
        file_rel = item["file"]
        env = item["env"]
        json_error = item["json_error"]

        base_cat, base_reason, base_warnings = _classify(
            validator=validator,
            src=src,
            path=p,
            file_rel=file_rel,
            env=env,
            json_error=json_error,
            cfg=baseline_cfg,
            quota_sim_runs_used=baseline_quota_sim_runs_used,
            workspace=repo_root,
        )
        cand_cat, cand_reason, cand_warnings = _classify(
            validator=validator,
            src=src,
            path=p,
            file_rel=file_rel,
            env=env,
            json_error=json_error,
            cfg=candidate_cfg,
            quota_sim_runs_used=candidate_quota_sim_runs_used,
            workspace=repo_root,
        )

        if base_cat == cand_cat:
            continue

        from_key = cat_short.get(base_cat, base_cat)
        to_key = cat_short.get(cand_cat, cand_cat)
        tkey = f"{from_key}_to_{to_key}"
        diff_counts[tkey] = int(diff_counts.get(tkey, 0)) + 1

        if tkey not in examples:
            examples[tkey] = []
        if len(examples[tkey]) < 5:
            request_id = _safe_str(env.get("request_id")) if isinstance(env, dict) else None
            intent = _safe_str(env.get("intent")) if isinstance(env, dict) else None
            examples[tkey].append(
                {
                    "file_or_path": file_rel,
                    "request_id": request_id,
                    "intent": intent,
                    "reason_baseline": base_reason,
                    "reason_candidate": cand_reason,
                    "warnings_baseline": base_warnings,
                    "warnings_candidate": cand_warnings,
                }
            )

    for k in list(examples.keys()):
        examples[k] = sorted(examples[k], key=lambda e: (str(e.get("file_or_path", "")), str(e.get("request_id") or "")))

    report = {
        "baseline_ref": baseline_ref,
        "baseline_available": True,
        "source": args.source,
        "inputs_total": len(unique_inputs),
        "inputs_breakdown": {"fixtures": len(fixture_paths), "evidence": len(evidence_paths)},
        "baseline": {
            "threshold_used": baseline_cfg.threshold_used,
            "routes": len(baseline_cfg.mapping),
            "policies_hash": baseline_cfg.policies_hash,
        },
        "candidate": {
            "threshold_used": candidate_cfg.threshold_used,
            "routes": len(candidate_cfg.mapping),
            "policies_hash": candidate_cfg.policies_hash,
        },
        "diff_counts": diff_counts,
        "examples": examples,
    }

    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

