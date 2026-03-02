from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        return str(path.resolve().as_posix())


def _policy_rel_label(workspace_root: Path, path: Path) -> str:
    root = _repo_root()
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        try:
            return str(path.resolve().relative_to(root.resolve()).as_posix())
        except Exception:
            return str(path.resolve().as_posix())


def write_subject_plan_summary(
    *,
    workspace_root: Path,
    plan: dict[str, Any],
    plan_rel: str,
    subject_id: str,
    themes: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> str:
    summary_path = workspace_root / ".cache" / "reports" / "north_star_subject_plan_summary.v1.md"
    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    coverage = decision.get("coverage") if isinstance(decision.get("coverage"), dict) else {}
    quality_gate = decision.get("quality_gate") if isinstance(decision.get("quality_gate"), dict) else {}
    thresholds = quality_gate.get("thresholds") if isinstance(quality_gate.get("thresholds"), dict) else {}
    actuals = quality_gate.get("actuals") if isinstance(quality_gate.get("actuals"), dict) else {}
    scoring_weights = thresholds.get("scoring_weights") if isinstance(thresholds.get("scoring_weights"), dict) else {}

    lines: list[str] = [
        "# North Star Subject Plan Summary",
        "",
        f"- plan_id: {plan.get('plan_id', '')}",
        f"- created_at: {plan.get('created_at', '')}",
        f"- subject_id: {subject_id}",
        f"- plan_path: {plan_rel}",
        f"- theme_count: {coverage.get('theme_count', 0)}",
        f"- subtheme_count: {coverage.get('subtheme_count', 0)}",
        f"- module_count: {decision.get('module_count', 0)}",
        f"- coverage_complete: {coverage.get('is_complete', False)}",
        f"- coverage_quality_score: {coverage.get('coverage_quality_score', 0)}",
        "",
        "## Quality Gate",
        f"- status: {quality_gate.get('status', 'UNKNOWN')}",
        f"- enforced: {quality_gate.get('enforced', False)}",
        f"- enforced_result: {quality_gate.get('enforced_result', False)}",
        f"- max_module_count: {thresholds.get('max_module_count', '')}",
        f"- min_coverage_quality: {thresholds.get('min_coverage_quality', '')}",
        f"- require_full_coverage: {thresholds.get('require_full_coverage', '')}",
        f"- scoring_pair_weight: {scoring_weights.get('pair_weight', '')}",
        f"- scoring_theme_weight: {scoring_weights.get('theme_weight', '')}",
        f"- scoring_completeness_weight: {scoring_weights.get('completeness_weight', '')}",
        f"- actual_module_count: {actuals.get('module_count', '')}",
        f"- actual_coverage_quality_score: {actuals.get('coverage_quality_score', '')}",
        "",
        "## Theme/Subtheme Catalog",
    ]

    if not themes:
        lines.append("- (none)")
    for theme in themes:
        theme_id = _safe_str(theme.get("theme_id"))
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        sub_ids = ", ".join(_safe_str(item.get("subtheme_id")) for item in subthemes if isinstance(item, dict)) or "-"
        lines.append(f"- {theme_id}: {sub_ids}")

    lines.append("")
    lines.append("## Module Plan")
    if not modules:
        lines.append("- (none)")
    for module in modules:
        module_id = _safe_str(module.get("module_id"))
        coverage_item = module.get("coverage") if isinstance(module.get("coverage"), dict) else {}
        theme_ids = module.get("covered_theme_ids") if isinstance(module.get("covered_theme_ids"), list) else []
        pairs = module.get("covered_subtheme_pairs") if isinstance(module.get("covered_subtheme_pairs"), list) else []
        pair_labels = ", ".join(
            f"{_safe_str(item.get('theme_id'))}/{_safe_str(item.get('subtheme_id'))}"
            for item in pairs
            if isinstance(item, dict)
        )
        lines.append(
            (
                f"- {module_id}: themes={','.join(str(x) for x in theme_ids)} "
                f"subtheme_pairs={coverage_item.get('subtheme_pair_count', 0)} "
                f"[{pair_labels or '-'}]"
            )
        )

    lines.append("")
    lines.append("## Coverage")
    lines.append(f"- covered_theme_ids: {', '.join(coverage.get('covered_theme_ids', [])) or '-'}")
    uncovered_themes = coverage.get("uncovered_theme_ids") if isinstance(coverage.get("uncovered_theme_ids"), list) else []
    lines.append(f"- uncovered_theme_ids: {', '.join(str(x) for x in uncovered_themes) or '-'}")
    uncovered_pairs = (
        coverage.get("uncovered_theme_subtheme_pairs")
        if isinstance(coverage.get("uncovered_theme_subtheme_pairs"), list)
        else []
    )
    if uncovered_pairs:
        pair_text = ", ".join(
            f"{_safe_str(item.get('theme_id'))}/{_safe_str(item.get('subtheme_id'))}"
            for item in uncovered_pairs
            if isinstance(item, dict)
        )
    else:
        pair_text = "-"
    lines.append(f"- uncovered_theme_subtheme_pairs: {pair_text}")

    lines.append("")
    lines.append("## Steps")
    for step in plan.get("steps", []) if isinstance(plan.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        ops = step.get("ops") if isinstance(step.get("ops"), list) else []
        lines.append(f"- {step.get('step_id', '')}: {step.get('type', '')} -> {', '.join(str(op) for op in ops)}")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _rel_path(workspace_root, summary_path)


def validate_subject_plan_contract(
    *,
    workspace_root: Path,
    plan_obj: dict[str, Any],
) -> tuple[bool, list[str], str]:
    schema_path = _repo_root() / "schemas" / "north-star-subject-plan.schema.v1.json"
    schema_label = _policy_rel_label(workspace_root, schema_path)
    if not schema_path.exists():
        return False, ["contract_schema_missing"], schema_label

    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return False, ["contract_validator_missing:jsonschema"], schema_label

    try:
        schema_obj = _load_json(schema_path)
    except Exception:
        return False, ["contract_schema_invalid_json"], schema_label
    if not isinstance(schema_obj, dict):
        return False, ["contract_schema_invalid_object"], schema_label

    try:
        validator = Draft202012Validator(schema_obj)
    except Exception:
        return False, ["contract_schema_invalid_definition"], schema_label

    errors = sorted(validator.iter_errors(plan_obj), key=lambda err: list(err.path))
    if not errors:
        return True, ["contract_validation=pass"], schema_label

    notes: list[str] = []
    for err in errors[:10]:
        path = "/".join(str(part) for part in err.path) or "$"
        message = str(err.message).replace("\n", " ").strip()
        notes.append(f"contract_error:{path}:{message}")
    if len(errors) > 10:
        notes.append(f"contract_error_truncated:{len(errors)}")
    return False, notes, schema_label
