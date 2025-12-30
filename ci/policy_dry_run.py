import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", required=True)
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

    fixtures_dir = Path(args.fixtures)
    fixture_paths = sorted(fixtures_dir.glob("*.json"), key=lambda p: p.name)
    if not fixture_paths:
        raise SystemExit("No fixture envelopes found.")

    categories = ["allow", "suspend", "block_unknown_intent", "invalid_envelope"]
    counts = {k: 0 for k in categories}
    examples: dict[str, list[dict]] = {k: [] for k in categories}

    for fixture_path in fixture_paths:
        file_rel = _relpath(fixture_path, repo_root)
        env = None
        json_error = None
        try:
            env = load_json(fixture_path)
        except Exception as e:
            json_error = str(e)

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
            elif _is_invalid_fixture_filename(fixture_path):
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
        "threshold_used": threshold_used,
        "counts": counts,
        "examples": examples,
    }

    Path(args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
