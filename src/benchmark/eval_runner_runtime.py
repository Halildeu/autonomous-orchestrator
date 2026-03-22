from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.integrity_utils import load_policy_integrity
from src.benchmark.eval_runner import (
    _build_ai_ops_fit_findings,
    _build_github_ops_release_findings,
    _build_integration_coherence_findings,
    _build_operability_findings,
    _build_trend_best_practice_findings,
    _deep_merge,
    _ensure_inside_workspace,
    _load_json,
    _now_iso,
    _safe_load_catalog_items,
    _write_if_missing,
)

_DEFAULT_DIMENSION_MAP = {
    "trend_best_practice": "A",
    "integrity_compat": "B",
    "ai_ops_fit": "C",
    "github_ops_release": "D",
    "operability": "E",
    "integration_coherence": "F",
    "context_health": "G",
}

_DEFAULT_MATURITY_LEVELS: list[dict[str, Any]] = [
    {
        "id": "L1",
        "label": "Foundation",
        "description": "Signal visibility is basic and mostly reactive.",
        "min_score": 0.0,
        "max_score": 0.24,
        "criteria": ["Core signals are partially present", "Most checks are manual"],
    },
    {
        "id": "L2",
        "label": "Managed",
        "description": "Signals are consistently produced with limited automation.",
        "min_score": 0.25,
        "max_score": 0.49,
        "criteria": ["Critical checks are repeatable", "Partial gate automation exists"],
    },
    {
        "id": "L3",
        "label": "Defined",
        "description": "Process and execution controls are standardized.",
        "min_score": 0.5,
        "max_score": 0.69,
        "criteria": ["Policy-driven execution is standard", "Evidence paths are stable"],
    },
    {
        "id": "L4",
        "label": "Measured",
        "description": "Quality and flow are tracked with proactive remediation.",
        "min_score": 0.7,
        "max_score": 0.84,
        "criteria": ["Lens-based scoring drives backlog", "Regression loops are controlled"],
    },
    {
        "id": "L5",
        "label": "Autonomous",
        "description": "End-to-end execution is deterministic and continuously optimized.",
        "min_score": 0.85,
        "max_score": 1.0,
        "criteria": ["Quality bar is consistently enforced", "Execution is mostly self-healing"],
    },
]


def _load_policy_north_star_eval_lenses(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    defaults = {
        "version": "v1",
        "mode": "lenses",
        "workflow_axes": ["reference", "assessment", "gap"],
        "dimension_map": dict(_DEFAULT_DIMENSION_MAP),
        "maturity_tracking": {
            "enabled": True,
            "output_path": ".cache/index/north_star_maturity_tracking.v1.json",
            "levels": list(_DEFAULT_MATURITY_LEVELS),
        },
    }
    ws_policy = workspace_root / "policies" / "policy_north_star_eval_lenses.v1.json"
    core_policy = core_root / "policies" / "policy_north_star_eval_lenses.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults
    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults
    merged = dict(defaults)
    for key, value in obj.items():
        merged[key] = value
    return merged


def _load_policy_north_star_operability(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    defaults = {
        "version": "v1",
        "heartbeat_expectation_mode": "ALWAYS",
        "thresholds": {
            "hard_exceeded_must_be": 0,
            "soft_target": 0,
            "soft_warn": 1,
            "placeholders_warn": 25,
            "placeholders_fail": 200,
            "docs_ops_md_count_warn": 40,
            "docs_ops_md_count_fail": 80,
            "docs_ops_md_bytes_warn": 250000,
            "docs_ops_md_bytes_fail": 500000,
            "repo_md_total_count_warn": 300,
            "repo_md_total_count_fail": 800,
            "docs_unmapped_md_warn": 1,
            "docs_unmapped_md_fail": 5,
            "jobs_stuck_warn": 1,
            "jobs_stuck_fail": 5,
            "jobs_fail_warn": 3,
            "jobs_fail_fail": 10,
            "pdca_cursor_stale_hours_warn": 24,
            "pdca_cursor_stale_hours_fail": 72,
            "heartbeat_stale_seconds_warn": 1800,
            "heartbeat_stale_seconds_fail": 7200,
            "intake_new_items_per_day_warn": 25,
            "intake_new_items_per_day_fail": 100,
            "suppressed_per_day_warn": 200,
        },
        "signals": {
            "script_budget": True,
            "doc_nav_placeholders": True,
            "docs_hygiene": True,
            "docs_drift": True,
            "airunner_jobs": True,
            "pdca_cursor": True,
            "airunner_heartbeat": True,
            "work_intake_noise": True,
            "integrity_pass_required": True,
        },
        "classification": {"FAIL_if": {}, "WARN_if": {}},
        "gap_rules": {},
    }
    core_policy = core_root / "policies" / "policy_north_star_operability.v1.json"
    ws_policy = workspace_root / "policies" / "policy_north_star_operability.v1.json"
    ws_override = workspace_root / ".cache" / "policy_overrides" / "policy_north_star_operability.override.v1.json"

    policy = defaults
    if core_policy.exists():
        try:
            obj = _load_json(core_policy)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            policy = defaults
    if ws_policy.exists():
        try:
            obj = _load_json(ws_policy)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            pass
    if ws_override.exists():
        try:
            obj = _load_json(ws_override)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            pass
    return policy


def _load_policy_north_star_integration_coherence(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    defaults = {
        "version": "v1",
        "thresholds": {
            "layer_boundary_violations_warn": 0,
            "layer_boundary_violations_fail": 0,
            "pack_conflicts_warn": 0,
            "pack_conflicts_fail": 0,
            "core_unlock_scope_widen_warn": 0,
            "core_unlock_scope_widen_fail": 1,
            "schema_fail_warn": 0,
            "schema_fail_fail": 1,
        },
        "signals": {
            "layer_boundary_report": True,
            "pack_validation_report": True,
            "core_unlock_compliance": True,
            "schema_validation_summary": True,
        },
        "classification": {"FAIL_if": {}, "WARN_if": {}},
        "gap_rules": {},
    }
    ws_policy = workspace_root / "policies" / "policy_north_star_integration_coherence.v1.json"
    core_policy = core_root / "policies" / "policy_north_star_integration_coherence.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults
    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults
    merged = dict(defaults)
    for key, value in obj.items():
        merged[key] = value
    return merged


def _compute_context_health_lens(*, workspace_root: Path, lenses_policy: dict[str, Any]) -> dict[str, Any]:
    """Compute Eval-G: Context Health lens score from 5 components."""
    ctx_cfg = lenses_policy.get("context_health") if isinstance(lenses_policy.get("context_health"), dict) else {}
    min_ok = float(ctx_cfg.get("min_score_ok", 0.8))
    min_warn = float(ctx_cfg.get("min_score_warn", 0.5))

    components: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []

    # Component 1: Session Freshness (0-20)
    session_score = 0
    try:
        from src.session.context_store import SessionPaths, is_expired, load_context
        sp = SessionPaths(workspace_root=workspace_root, session_id="default")
        if sp.context_path.exists():
            ctx = load_context(sp.context_path)
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if not is_expired(ctx, now_iso):
                session_score = 20
            else:
                reasons.append("session_expired")
                session_score = 0
        else:
            reasons.append("session_missing")
    except Exception:
        reasons.append("session_check_failed")
    components["session_freshness"] = {"score": session_score, "max": 20}

    # Component 2: Decision Coverage (0-20)
    decision_score = 0
    try:
        from src.session.context_store import SessionPaths as _SP, load_context as _lc
        sp = _SP(workspace_root=workspace_root, session_id="default")
        if sp.context_path.exists():
            ctx = _lc(sp.context_path)
            decisions = ctx.get("ephemeral_decisions", [])
            if isinstance(decisions, list) and len(decisions) > 0:
                decision_score = min(20, len(decisions) * 4)  # 5+ decisions = full score
            else:
                reasons.append("no_decisions")
    except Exception:
        pass
    components["decision_coverage"] = {"score": decision_score, "max": 20}

    # Component 3: Standards Compliance (0-20)
    standards_score = 0
    lock_path = workspace_root / "standards.lock"
    if not lock_path.exists():
        # Check parent repo
        try:
            repo_root = Path(__file__).resolve().parents[2]
            if (repo_root / "standards.lock").exists():
                standards_score = 20
            else:
                reasons.append("standards_lock_missing")
        except Exception:
            reasons.append("standards_lock_check_failed")
    else:
        standards_score = 20
    components["standards_compliance"] = {"score": standards_score, "max": 20}

    # Component 4: Artifact Completeness (0-20)
    artifact_paths = [
        ".cache/index/gap_register.v1.json",
        ".cache/index/work_intake.v1.json",
        ".cache/reports/system_status.v1.json",
        ".cache/index/extension_registry.v1.json",
        ".cache/index/session_cross_context.v1.json",
    ]
    present = sum(1 for p in artifact_paths if (workspace_root / p).exists())
    artifact_score = int((present / len(artifact_paths)) * 20)
    if present < len(artifact_paths):
        reasons.append(f"missing_{len(artifact_paths) - present}_artifacts")
    components["artifact_completeness"] = {"score": artifact_score, "max": 20}

    # Component 5: Drift Score (0-20) — uses cached drift report if available
    drift_score = 20  # Default: no drift detected
    drift_report_path = workspace_root / ".cache" / "reports" / "context_drift_report.v1.json"
    if drift_report_path.exists():
        try:
            import json as _json
            drift_data = _json.loads(drift_report_path.read_text(encoding="utf-8"))
            drift_score = int(drift_data.get("drift_score", 0)) // 5  # 0-100 → 0-20
            drift_score = min(20, max(0, drift_score))
            if drift_data.get("status") != "OK":
                reasons.append(f"drift_detected_{drift_data.get('total_drifted', 0)}")
        except Exception:
            pass
    components["drift_score"] = {"score": drift_score, "max": 20}

    # Component 6: Extension Health (0-20) — enabled extensions with present outputs
    ext_health_score = 20  # Default: no extensions or all healthy
    try:
        from src.ops.extension_context_bridge import collect_extension_output_paths
        ext_output_paths = collect_extension_output_paths(workspace_root)
        if ext_output_paths:
            present = sum(1 for p in ext_output_paths if (workspace_root / p).exists())
            ext_health_score = int((present / len(ext_output_paths)) * 20)
            missing_ext = len(ext_output_paths) - present
            if missing_ext > 0:
                reasons.append(f"missing_{missing_ext}_extension_outputs")
    except Exception:
        pass
    components["extension_health"] = {"score": ext_health_score, "max": 20}

    # Total score: sum of 6 components (0-120) → normalize to 0.0-1.0
    total = sum(c["score"] for c in components.values())
    normalized = total / 120.0

    status = _lens_status(normalized, min_ok, min_warn)

    return {
        "status": status,
        "score": round(normalized, 4),
        "components": {k: v for k, v in components.items()},
        "reasons": reasons,
    }


def _lens_status(score: float, min_ok: float, min_warn: float) -> str:
    if score >= min_ok:
        return "OK"
    if score >= min_warn:
        return "WARN"
    return "FAIL"


def _ensure_catalogs(workspace_root: Path, *, allow_write: bool) -> tuple[Path, Path, int, int]:
    bp_path = workspace_root / ".cache" / "index" / "bp_catalog.v1.json"
    trend_path = workspace_root / ".cache" / "index" / "trend_catalog.v1.json"

    bp_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": [],
    }
    trend_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": [],
    }
    if allow_write:
        _write_if_missing(bp_path, bp_payload)
        _write_if_missing(trend_path, trend_payload)

    bp_items = 0
    trend_items = 0
    if bp_path.exists():
        try:
            obj = _load_json(bp_path)
            items = obj.get("items") if isinstance(obj, dict) else None
            bp_items = len(items) if isinstance(items, list) else 0
        except Exception:
            bp_items = 0
    if trend_path.exists():
        try:
            obj = _load_json(trend_path)
            items = obj.get("items") if isinstance(obj, dict) else None
            trend_items = len(items) if isinstance(items, list) else 0
        except Exception:
            trend_items = 0

    return bp_path, trend_path, bp_items, trend_items


def _safe_unit_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    if parsed < 0.0:
        return 0.0
    if parsed > 1.0:
        return 1.0
    return parsed


def _normalized_dimension_map(lenses_policy: dict[str, Any]) -> dict[str, str]:
    raw = lenses_policy.get("dimension_map")
    if not isinstance(raw, dict):
        return dict(_DEFAULT_DIMENSION_MAP)
    out = dict(_DEFAULT_DIMENSION_MAP)
    allowed = {"A", "B", "C", "D", "E", "F", "G"}
    for lens_id in _DEFAULT_DIMENSION_MAP.keys():
        value = raw.get(lens_id)
        if isinstance(value, str) and value in allowed:
            out[lens_id] = value
    return out


def _normalized_maturity_levels(lenses_policy: dict[str, Any]) -> list[dict[str, Any]]:
    mt = lenses_policy.get("maturity_tracking") if isinstance(lenses_policy.get("maturity_tracking"), dict) else {}
    raw_levels = mt.get("levels")
    source = raw_levels if isinstance(raw_levels, list) else list(_DEFAULT_MATURITY_LEVELS)
    out: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        level_id = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not level_id or not label:
            continue
        criteria_raw = item.get("criteria")
        criteria = [str(x).strip() for x in criteria_raw if isinstance(x, str) and str(x).strip()] if isinstance(
            criteria_raw, list
        ) else []
        min_score = _safe_unit_float(item.get("min_score"), 0.0)
        max_score = _safe_unit_float(item.get("max_score"), 1.0)
        if max_score < min_score:
            min_score, max_score = max_score, min_score
        level_obj: dict[str, Any] = {
            "id": level_id,
            "label": label,
            "criteria": criteria,
            "min_score": round(min_score, 4),
            "max_score": round(max_score, 4),
        }
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            level_obj["description"] = description.strip()
        out.append(level_obj)
    if not out:
        return list(_DEFAULT_MATURITY_LEVELS)
    out.sort(key=lambda item: float(item.get("min_score", 0.0)))
    return out


def _maturity_level_for_score(levels: list[dict[str, Any]], score: float) -> dict[str, Any]:
    if not levels:
        return {
            "id": "L0",
            "label": "Unknown",
            "criteria": [],
            "min_score": 0.0,
            "max_score": 1.0,
        }
    for item in levels:
        min_score = _safe_unit_float(item.get("min_score"), 0.0)
        max_score = _safe_unit_float(item.get("max_score"), 1.0)
        if min_score <= score <= max_score:
            return item
    if score < _safe_unit_float(levels[0].get("min_score"), 0.0):
        return levels[0]
    return levels[-1]


def _build_maturity_document(
    *,
    workspace_root: Path,
    lenses_policy: dict[str, Any],
    mode: str,
    coverage: float,
    lens_scores: dict[str, dict[str, Any]],
    fallback_score: float,
) -> dict[str, Any]:
    dimension_map = _normalized_dimension_map(lenses_policy)
    levels = _normalized_maturity_levels(lenses_policy)
    has_lens_scores = any(isinstance(lens_scores.get(lens_id), dict) for lens_id in dimension_map.keys())
    dimensions: list[dict[str, Any]] = []
    if has_lens_scores:
        ordered_pairs = sorted(dimension_map.items(), key=lambda item: (str(item[1]), str(item[0])))
        for lens_id, dimension in ordered_pairs:
            lens = lens_scores.get(lens_id) if isinstance(lens_scores.get(lens_id), dict) else {}
            status = str(lens.get("status") or "UNKNOWN").upper()
            if status not in {"OK", "WARN", "FAIL"}:
                status = "UNKNOWN"
            score = _safe_unit_float(lens.get("score"), 0.0)
            dimensions.append(
                {
                    "dimension": dimension,
                    "lens_id": lens_id,
                    "status": status,
                    "score": round(score, 4),
                }
            )

    if has_lens_scores and dimensions:
        maturity_score = round(sum(float(item.get("score", 0.0)) for item in dimensions) / float(len(dimensions)), 4)
    else:
        maturity_score = round(_safe_unit_float(fallback_score), 4)

    current_level = _maturity_level_for_score(levels, maturity_score)
    return {
        "version": "v1",
        "levels": levels,
        "tracking": {
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "mode": mode,
            "source_eval_ref": str(Path(".cache") / "index" / "assessment_eval.v1.json"),
            "score": maturity_score,
            "coverage": round(_safe_unit_float(coverage), 4),
            "current_level_id": str(current_level.get("id") or "L0"),
            "current_level_label": str(current_level.get("label") or "Unknown"),
            "dimensions": dimensions,
            "notes": [],
        },
    }


def run_eval(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    _ensure_inside_workspace(workspace_root, eval_path)

    bp_path, trend_path, bp_items, trend_items = _ensure_catalogs(workspace_root, allow_write=not dry_run)

    notes: list[str] = []
    report_only = False
    status = "OK"
    controls = 0
    metrics = 0
    raw: dict[str, Any] = {}
    integrity_snapshot_ref = str(Path(".cache") / "reports" / "integrity_verify.v1.json")

    raw_ref = str(Path(".cache") / "index" / "assessment_raw.v1.json")
    if raw_path.exists():
        try:
            raw = _load_json(raw_path)
            inputs = raw.get("inputs") if isinstance(raw, dict) else None
            controls = int(inputs.get("controls") or 0) if isinstance(inputs, dict) else 0
            metrics = int(inputs.get("metrics") or 0) if isinstance(inputs, dict) else 0
            ref = raw.get("integrity_snapshot_ref") if isinstance(raw, dict) else None
            if isinstance(ref, str) and ref.strip():
                integrity_snapshot_ref = ref
        except Exception:
            status = "WARN"
            notes.append("invalid_raw")
    else:
        status = "SKIPPED"
        report_only = True
        notes.append("raw_missing")

    integrity_status = None
    integrity_path = workspace_root / integrity_snapshot_ref
    if integrity_path.exists():
        try:
            obj = _load_json(integrity_path)
            integrity_status = obj.get("verify_on_read_result") if isinstance(obj, dict) else None
        except Exception:
            integrity_status = None
    else:
        integrity_status = "FAIL"
        notes.append("integrity_snapshot_missing")

    policy = load_policy_integrity(core_root=core_root, workspace_root=workspace_root)
    allow_report_only = bool(policy.get("allow_report_only_when_missing_sources", True))
    if integrity_status == "FAIL":
        if allow_report_only:
            status = "WARN" if status != "SKIPPED" else status
            report_only = True
            notes.append("integrity_report_only")
        else:
            status = "SKIPPED"
            report_only = True
            notes.append("integrity_blocked")

    total = controls + metrics
    maturity_avg = 0.0
    coverage = 0.0 if total <= 0 else min(1.0, float(bp_items + trend_items) / float(total))

    lenses_policy = _load_policy_north_star_eval_lenses(core_root=core_root, workspace_root=workspace_root)
    eval_mode = str(lenses_policy.get("mode") or "").strip().lower()
    if eval_mode == "lensless":
        workflow_axes_raw = (
            lenses_policy.get("workflow_axes") if isinstance(lenses_policy.get("workflow_axes"), list) else []
        )
        workflow_axes = [str(x).strip().lower() for x in workflow_axes_raw if isinstance(x, str) and str(x).strip()]
        if not workflow_axes:
            workflow_axes = ["reference", "assessment", "gap"]

        integrity_state = str(integrity_status or "UNKNOWN").strip().upper()
        if integrity_state not in {"PASS", "WARN", "FAIL"}:
            integrity_state = "UNKNOWN"

        assessment_payload = {
            "workflow_axes": workflow_axes,
            "integrity_status": integrity_state,
            "raw_present": bool(raw_path.exists()),
            "reference_catalog_items": int(bp_items + trend_items),
            "notes": sorted(set(notes)),
        }
        integrity_component = 1.0 if integrity_state == "PASS" else (0.5 if integrity_state == "WARN" else 0.0)
        raw_component = 1.0 if bool(raw_path.exists()) else 0.0
        catalog_component = _safe_unit_float(coverage, 0.0)
        maturity_avg = round((integrity_component + raw_component + catalog_component) / 3.0, 4)
        maturity_doc = _build_maturity_document(
            workspace_root=workspace_root,
            lenses_policy=lenses_policy,
            mode="lensless",
            coverage=coverage,
            lens_scores={},
            fallback_score=maturity_avg,
        )
        maturity_avg = _safe_unit_float(
            (maturity_doc.get("tracking") if isinstance(maturity_doc.get("tracking"), dict) else {}).get("score"),
            maturity_avg,
        )

        payload = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": status,
            "report_only": bool(report_only),
            "integrity_snapshot_ref": str(integrity_snapshot_ref),
            "raw_ref": str(raw_ref),
            "bp_catalog_ref": str(Path(".cache") / "index" / "bp_catalog.v1.json"),
            "trend_catalog_ref": str(Path(".cache") / "index" / "trend_catalog.v1.json"),
            "scores": {"maturity_avg": round(maturity_avg, 4), "coverage": round(coverage, 4)},
            "inputs": {"controls": controls, "metrics": metrics, "bp_items": bp_items, "trend_items": trend_items},
            "assessment": assessment_payload,
            "maturity_tracking": maturity_doc,
            "notes": sorted(set(notes)),
        }

        schema_path = core_root / "schemas" / "assessment-eval.schema.v1.json"
        if schema_path.exists():
            schema = _load_json(schema_path)
            Draft202012Validator(schema).validate(payload)

        if dry_run:
            return {
                "status": "WOULD_WRITE",
                "out": str(eval_path),
                "report_only": report_only,
            }

        eval_path.parent.mkdir(parents=True, exist_ok=True)
        eval_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "OK",
            "out": str(eval_path),
            "report_only": report_only,
        }

    trend_policy = lenses_policy.get("trend_best_practice") if isinstance(lenses_policy.get("trend_best_practice"), dict) else {}
    integrity_policy = lenses_policy.get("integrity_compat") if isinstance(lenses_policy.get("integrity_compat"), dict) else {}
    ai_ops_policy = lenses_policy.get("ai_ops_fit") if isinstance(lenses_policy.get("ai_ops_fit"), dict) else {}
    gh_ops_policy = (
        lenses_policy.get("github_ops_release") if isinstance(lenses_policy.get("github_ops_release"), dict) else {}
    )

    min_cov_ok = float(trend_policy.get("min_coverage_ok", 0.5) or 0.5)
    min_cov_warn = float(trend_policy.get("min_coverage_warn", 0.2) or 0.2)
    trend_status = _lens_status(float(coverage), min_cov_ok, min_cov_warn)

    integrity_score = 0.0
    if integrity_status == "PASS":
        integrity_score = 1.0
    elif integrity_status == "WARN":
        integrity_score = 0.5
    else:
        integrity_score = 0.0
    min_int_ok = float(integrity_policy.get("min_score_ok", 1.0) or 1.0)
    min_int_warn = float(integrity_policy.get("min_score_warn", 0.5) or 0.5)
    integrity_lens_status = _lens_status(integrity_score, min_int_ok, min_int_warn)

    required_fields = ai_ops_policy.get("required_fields")
    if not isinstance(required_fields, list):
        required_fields = ["context_pack_present", "provider_policy_pinned", "secrets_redacted"]
    context_pack_present = (workspace_root / ".cache" / "index" / "context_pack.v1.json").exists()
    provider_policy_pinned = (core_root / "policies" / "policy_llm_providers_guardrails.v1.json").exists()
    secrets_redacted = (core_root / "policies" / "policy_secrets.v1.json").exists()
    req_map = {
        "context_pack_present": context_pack_present,
        "provider_policy_pinned": provider_policy_pinned,
        "secrets_redacted": secrets_redacted,
    }
    required_list = [str(x) for x in required_fields if isinstance(x, str) and x.strip()]
    if required_list:
        score_hits = sum(1 for key in required_list if req_map.get(key))
        ai_ops_score = score_hits / float(len(required_list))
    else:
        ai_ops_score = 0.0
    min_ai_ok = float(ai_ops_policy.get("min_score_ok", 1.0) or 1.0)
    min_ai_warn = float(ai_ops_policy.get("min_score_warn", 0.5) or 0.5)
    ai_ops_status = _lens_status(ai_ops_score, min_ai_ok, min_ai_warn)

    gh_policy_path = workspace_root / "policies" / "policy_github_ops.v1.json"
    if not gh_policy_path.exists():
        gh_policy_path = core_root / "policies" / "policy_github_ops.v1.json"
    release_policy_path = workspace_root / "policies" / "policy_release_automation.v1.json"
    if not release_policy_path.exists():
        release_policy_path = core_root / "policies" / "policy_release_automation.v1.json"

    gh_policy_present = gh_policy_path.exists()
    release_policy_present = release_policy_path.exists()
    github_jobs_index_present = (workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json").exists()
    release_manifest_present = (workspace_root / ".cache" / "reports" / "release_manifest.v1.json").exists()

    github_ops_network_default_off = False
    if gh_policy_present:
        try:
            gh_policy_obj = _load_json(gh_policy_path)
            github_ops_network_default_off = gh_policy_obj.get("network_enabled") is False
        except Exception:
            github_ops_network_default_off = False

    gh_required_fields = gh_ops_policy.get("required_fields")
    if not isinstance(gh_required_fields, list):
        gh_required_fields = [
            "github_ops_policy_present",
            "github_ops_network_default_off",
            "release_policy_present",
            "github_jobs_index_present",
            "release_manifest_present",
        ]
    gh_required_list = [str(x) for x in gh_required_fields if isinstance(x, str) and x.strip()]
    gh_requirements = {
        "github_ops_policy_present": bool(gh_policy_present),
        "github_ops_network_default_off": bool(github_ops_network_default_off),
        "release_policy_present": bool(release_policy_present),
        "github_jobs_index_present": bool(github_jobs_index_present),
        "release_manifest_present": bool(release_manifest_present),
    }
    if gh_required_list:
        gh_score_hits = sum(1 for key in gh_required_list if gh_requirements.get(key))
        gh_score = gh_score_hits / float(len(gh_required_list))
    else:
        gh_score = 0.0
    min_gh_ok = float(gh_ops_policy.get("min_score_ok", 1.0) or 1.0)
    min_gh_warn = float(gh_ops_policy.get("min_score_warn", 0.5) or 0.5)
    gh_status = _lens_status(gh_score, min_gh_ok, min_gh_warn)
    gh_notes = [f"missing:{key}" for key in gh_required_list if not gh_requirements.get(key)]

    operability_policy = _load_policy_north_star_operability(core_root=core_root, workspace_root=workspace_root)
    integration_policy = _load_policy_north_star_integration_coherence(core_root=core_root, workspace_root=workspace_root)
    operability_cfg = (
        lenses_policy.get("operability") if isinstance(lenses_policy.get("operability"), dict) else {}
    )
    integration_cfg = (
        lenses_policy.get("integration_coherence")
        if isinstance(lenses_policy.get("integration_coherence"), dict)
        else {}
    )
    operability_required_fields = operability_cfg.get("required_fields")
    if not isinstance(operability_required_fields, list):
        operability_required_fields = [
            "script_budget_present",
            "doc_nav_present",
            "docs_hygiene_present",
            "docs_drift_present",
            "airunner_jobs_present",
            "pdca_cursor_present",
            "heartbeat_present",
            "work_intake_present",
            "integrity_present",
        ]

    raw_signals = raw.get("signals") if isinstance(raw, dict) else {}
    raw_signals = raw_signals if isinstance(raw_signals, dict) else {}
    sb_signal = raw_signals.get("script_budget") if isinstance(raw_signals.get("script_budget"), dict) else {}
    doc_nav_signal = raw_signals.get("doc_nav") if isinstance(raw_signals.get("doc_nav"), dict) else {}
    docs_hygiene_signal = raw_signals.get("docs_hygiene") if isinstance(raw_signals.get("docs_hygiene"), dict) else {}
    docs_drift_signal = raw_signals.get("docs_drift") if isinstance(raw_signals.get("docs_drift"), dict) else {}
    airunner_state = (
        raw_signals.get("airrunner_state") if isinstance(raw_signals.get("airrunner_state"), dict) else {}
    )
    jobs_signal = raw_signals.get("airunner_jobs") if isinstance(raw_signals.get("airunner_jobs"), dict) else {}
    pdca_signal = raw_signals.get("pdca_cursor") if isinstance(raw_signals.get("pdca_cursor"), dict) else {}
    heartbeat_signal = (
        raw_signals.get("airunner_heartbeat") if isinstance(raw_signals.get("airunner_heartbeat"), dict) else {}
    )
    intake_signal = raw_signals.get("work_intake_noise") if isinstance(raw_signals.get("work_intake_noise"), dict) else {}
    integrity_signal = raw_signals.get("integrity") if isinstance(raw_signals.get("integrity"), dict) else {}
    integration_signals = (
        raw.get("integration_coherence_signals")
        if isinstance(raw.get("integration_coherence_signals"), dict)
        else {}
    )
    integration_signals_present = isinstance(raw.get("integration_coherence_signals"), dict)

    required_map = {
        "script_budget_present": isinstance(raw_signals.get("script_budget"), dict),
        "doc_nav_present": isinstance(raw_signals.get("doc_nav"), dict),
        "docs_hygiene_present": isinstance(raw_signals.get("docs_hygiene"), dict),
        "docs_drift_present": isinstance(raw_signals.get("docs_drift"), dict),
        "airunner_jobs_present": isinstance(raw_signals.get("airunner_jobs"), dict),
        "pdca_cursor_present": isinstance(raw_signals.get("pdca_cursor"), dict),
        "heartbeat_present": isinstance(raw_signals.get("airunner_heartbeat"), dict),
        "work_intake_present": isinstance(raw_signals.get("work_intake_noise"), dict),
        "integrity_present": isinstance(raw_signals.get("integrity"), dict),
    }
    operability_required_list = [str(x) for x in operability_required_fields if isinstance(x, str) and x.strip()]
    if operability_required_list:
        operability_score_hits = sum(1 for key in operability_required_list if required_map.get(key))
        operability_coverage = operability_score_hits / float(len(operability_required_list))
    else:
        operability_coverage = 0.0

    thresholds = operability_policy.get("thresholds") if isinstance(operability_policy.get("thresholds"), dict) else {}
    fail_cfg = (
        operability_policy.get("classification", {}).get("FAIL_if")
        if isinstance(operability_policy.get("classification"), dict)
        else {}
    )
    warn_cfg = (
        operability_policy.get("classification", {}).get("WARN_if")
        if isinstance(operability_policy.get("classification"), dict)
        else {}
    )

    hard_exceeded = int(sb_signal.get("hard_exceeded", 0) or 0)
    soft_exceeded = int(sb_signal.get("soft_exceeded", 0) or 0)
    placeholders = int(doc_nav_signal.get("placeholders_count", 0) or 0)
    broken_refs = int(doc_nav_signal.get("broken_refs", 0) or 0)
    orphan_critical = int(doc_nav_signal.get("orphan_critical", 0) or 0)
    docs_ops_md_count = int(docs_hygiene_signal.get("docs_ops_md_count", 0) or 0)
    docs_ops_md_bytes = int(docs_hygiene_signal.get("docs_ops_md_bytes", 0) or 0)
    repo_md_total_count = int(docs_hygiene_signal.get("repo_md_total_count", 0) or 0)
    docs_unmapped_md_count = int(docs_drift_signal.get("unmapped_md_count", 0) or 0)
    jobs_stuck = int(jobs_signal.get("stuck", 0) or 0)
    jobs_fail = int(jobs_signal.get("fail", 0) or 0)
    pdca_stale = float(pdca_signal.get("stale_hours", 0.0) or 0.0)
    heartbeat_stale = int(heartbeat_signal.get("stale_seconds", 0) or 0)
    airunner_enabled = bool(airunner_state.get("enabled_effective", False))
    auto_mode_enabled = bool(airunner_state.get("auto_mode_enabled_effective", False))
    heartbeat_capability = airunner_enabled or auto_mode_enabled
    heartbeat_expectation_mode = str(operability_policy.get("heartbeat_expectation_mode") or "ALWAYS").strip().upper()
    if heartbeat_expectation_mode not in {"ALWAYS", "ACTIVE_HOURS", "NONE"}:
        heartbeat_expectation_mode = "ALWAYS"
    active_hours_is_now = airunner_state.get("active_hours_is_now")
    active_hours_is_now_bool = bool(active_hours_is_now) if isinstance(active_hours_is_now, bool) else True
    if heartbeat_expectation_mode == "NONE":
        heartbeat_expected_now = False
    elif heartbeat_expectation_mode == "ACTIVE_HOURS":
        heartbeat_expected_now = heartbeat_capability and active_hours_is_now_bool
    else:
        heartbeat_expected_now = heartbeat_capability
    intake_new = int(intake_signal.get("new_items_24h", 0) or 0)
    suppressed = int(intake_signal.get("suppressed_24h", 0) or 0)
    integrity_status_signal = str(integrity_signal.get("status") or "")
    layer_boundary_violations = int(integration_signals.get("layer_boundary_violations_count", 0) or 0)
    pack_conflicts = int(integration_signals.get("pack_conflict_count", 0) or 0)
    core_unlock_scope_widen = int(integration_signals.get("core_unlock_scope_widen_count", 0) or 0)
    schema_fail_count = int(integration_signals.get("schema_fail_count", 0) or 0)

    trend_catalog_items = _safe_load_catalog_items(trend_path)
    bp_catalog_items = _safe_load_catalog_items(bp_path)
    trend_findings = _build_trend_best_practice_findings(
        workspace_root=workspace_root,
        raw_ref=raw_ref,
        thresholds=thresholds,
        facts={
            "hard_exceeded": hard_exceeded,
            "soft_exceeded": soft_exceeded,
            "placeholders": placeholders,
            "broken_refs": broken_refs,
            "orphan_critical": orphan_critical,
            "docs_unmapped_md_count": docs_unmapped_md_count,
            "pdca_stale_hours": pdca_stale,
            "heartbeat_stale_seconds": heartbeat_stale,
            "heartbeat_expected_now": bool(heartbeat_expected_now),
            "jobs_stuck": jobs_stuck,
            "jobs_fail": jobs_fail,
            "intake_new_items_24h": intake_new,
            "suppressed_24h": suppressed,
            "integrity_status": integrity_status_signal,
            "layer_boundary_violations": layer_boundary_violations,
            "pack_conflicts": pack_conflicts,
            "core_unlock_scope_widen": core_unlock_scope_widen,
            "schema_fail_count": schema_fail_count,
            "auto_mode_enabled": auto_mode_enabled,
        },
        trend_items=trend_catalog_items,
        bp_items=bp_catalog_items,
        evidence_paths={
            "script_budget_report_path": sb_signal.get("report_path"),
            "doc_nav_report_path": doc_nav_signal.get("report_path"),
            "heartbeat_path": heartbeat_signal.get("heartbeat_path"),
            "integrity_snapshot_ref": integrity_snapshot_ref,
            "core_unlock_compliance_path": str(Path(".cache") / "reports" / "core_unlock_compliance.v1.json"),
            "airrunner_jobs_index_path": jobs_signal.get("jobs_index_path"),
        },
    )

    def _resolve_threshold(value: Any) -> float:
        if isinstance(value, str):
            return float(thresholds.get(value, 0) or 0)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []
    reason_map = {
        "docs_ops_md_count_gt": "operability_docs_ops_md_count_gt",
        "docs_ops_md_bytes_gt": "operability_docs_ops_md_bytes_gt",
        "repo_md_total_count_gt": "operability_repo_md_total_count_gt",
        "docs_unmapped_md_gt": "operability_docs_unmapped_md_gt",
    }

    def _reason_code(key: str) -> str:
        return reason_map.get(key, key)

    ordered_checks = [
        "hard_exceeded_gt",
        "soft_exceeded_gt",
        "integrity_fail",
        "jobs_stuck_gt",
        "jobs_fail_gt",
        "pdca_cursor_stale_hours_gt",
        "heartbeat_stale_seconds_gt",
        "placeholders_gt",
        "docs_ops_md_count_gt",
        "docs_ops_md_bytes_gt",
        "repo_md_total_count_gt",
        "docs_unmapped_md_gt",
        "intake_new_items_per_day_gt",
        "suppressed_per_day_gt",
    ]
    for key in ordered_checks:
        if key in fail_cfg:
            if key == "integrity_fail" and bool(fail_cfg.get(key)) and integrity_status_signal == "FAIL":
                fail_reasons.append(_reason_code(key))
            elif key == "hard_exceeded_gt" and hard_exceeded > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "jobs_stuck_gt" and jobs_stuck > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "jobs_fail_gt" and jobs_fail > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "pdca_cursor_stale_hours_gt" and pdca_stale > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif (
                key == "heartbeat_stale_seconds_gt"
                and heartbeat_expected_now
                and heartbeat_stale > _resolve_threshold(fail_cfg.get(key))
            ):
                fail_reasons.append(_reason_code(key))
            elif key == "placeholders_gt" and placeholders > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "docs_ops_md_count_gt" and docs_ops_md_count > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "docs_ops_md_bytes_gt" and docs_ops_md_bytes > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "repo_md_total_count_gt" and repo_md_total_count > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "docs_unmapped_md_gt" and docs_unmapped_md_count > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "intake_new_items_per_day_gt" and intake_new > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
            elif key == "suppressed_per_day_gt" and suppressed > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(_reason_code(key))
        if key in warn_cfg:
            if key == "hard_exceeded_gt" and hard_exceeded > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "jobs_stuck_gt" and jobs_stuck > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "jobs_fail_gt" and jobs_fail > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "pdca_cursor_stale_hours_gt" and pdca_stale > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif (
                key == "heartbeat_stale_seconds_gt"
                and heartbeat_expected_now
                and heartbeat_stale > _resolve_threshold(warn_cfg.get(key))
            ):
                warn_reasons.append(_reason_code(key))
            elif key == "placeholders_gt" and placeholders > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "docs_ops_md_count_gt" and docs_ops_md_count > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "docs_ops_md_bytes_gt" and docs_ops_md_bytes > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "repo_md_total_count_gt" and repo_md_total_count > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "docs_unmapped_md_gt" and docs_unmapped_md_count > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "intake_new_items_per_day_gt" and intake_new > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "suppressed_per_day_gt" and suppressed > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))
            elif key == "soft_exceeded_gt" and soft_exceeded > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(_reason_code(key))

    if fail_reasons:
        operability_classification = "FAIL"
    elif warn_reasons:
        operability_classification = "WARN"
    else:
        operability_classification = "OK"

    operability_score = {"OK": 1.0, "WARN": 0.5, "FAIL": 0.0}[operability_classification]
    reasons = sorted(set(fail_reasons or warn_reasons))

    simplicity = 1.0
    if hard_exceeded > 0:
        simplicity = 0.0
    elif soft_exceeded > 0:
        simplicity = 0.5

    placeholders_warn = float(thresholds.get("placeholders_warn", 0) or 0)
    placeholders_fail = float(thresholds.get("placeholders_fail", 0) or 0)
    docs_ops_md_count_warn = float(thresholds.get("docs_ops_md_count_warn", 0) or 0)
    docs_ops_md_count_fail = float(thresholds.get("docs_ops_md_count_fail", 0) or 0)
    docs_ops_md_bytes_warn = float(thresholds.get("docs_ops_md_bytes_warn", 0) or 0)
    docs_ops_md_bytes_fail = float(thresholds.get("docs_ops_md_bytes_fail", 0) or 0)
    repo_md_total_count_warn = float(thresholds.get("repo_md_total_count_warn", 0) or 0)
    repo_md_total_count_fail = float(thresholds.get("repo_md_total_count_fail", 0) or 0)
    intake_warn = float(thresholds.get("intake_new_items_per_day_warn", 0) or 0)
    intake_fail = float(thresholds.get("intake_new_items_per_day_fail", 0) or 0)
    suppressed_warn = float(thresholds.get("suppressed_per_day_warn", 0) or 0)
    sustainability = 1.0
    if (
        placeholders > placeholders_fail
        or intake_new > intake_fail
        or docs_ops_md_count > docs_ops_md_count_fail
        or docs_ops_md_bytes > docs_ops_md_bytes_fail
        or repo_md_total_count > repo_md_total_count_fail
    ):
        sustainability = 0.0
    elif (
        placeholders > placeholders_warn
        or intake_new > intake_warn
        or suppressed > suppressed_warn
        or docs_ops_md_count > docs_ops_md_count_warn
        or docs_ops_md_bytes > docs_ops_md_bytes_warn
        or repo_md_total_count > repo_md_total_count_warn
    ):
        sustainability = 0.5

    jobs_stuck_warn = float(thresholds.get("jobs_stuck_warn", 0) or 0)
    jobs_stuck_fail = float(thresholds.get("jobs_stuck_fail", 0) or 0)
    jobs_fail_warn = float(thresholds.get("jobs_fail_warn", 0) or 0)
    jobs_fail_fail = float(thresholds.get("jobs_fail_fail", 0) or 0)
    pdca_warn = float(thresholds.get("pdca_cursor_stale_hours_warn", 0) or 0)
    pdca_fail = float(thresholds.get("pdca_cursor_stale_hours_fail", 0) or 0)
    heartbeat_warn = float(thresholds.get("heartbeat_stale_seconds_warn", 0) or 0)
    heartbeat_fail = float(thresholds.get("heartbeat_stale_seconds_fail", 0) or 0)

    continuity = 1.0
    if (
        integrity_status_signal == "FAIL"
        or jobs_stuck > jobs_stuck_fail
        or jobs_fail > jobs_fail_fail
        or pdca_stale > pdca_fail
        or (heartbeat_expected_now and heartbeat_stale > heartbeat_fail)
    ):
        continuity = 0.0
    elif (
        jobs_stuck > jobs_stuck_warn
        or jobs_fail > jobs_fail_warn
        or pdca_stale > pdca_warn
        or (heartbeat_expected_now and heartbeat_stale > heartbeat_warn)
    ):
        continuity = 0.5

    min_operability_ok = float(operability_cfg.get("min_score_ok", 1.0) or 1.0)
    min_operability_warn = float(operability_cfg.get("min_score_warn", 0.5) or 0.5)
    operability_status = _lens_status(float(operability_score), min_operability_ok, min_operability_warn)

    integration_thresholds = (
        integration_policy.get("thresholds") if isinstance(integration_policy.get("thresholds"), dict) else {}
    )
    integration_fail_cfg = (
        integration_policy.get("classification", {}).get("FAIL_if")
        if isinstance(integration_policy.get("classification"), dict)
        else {}
    )
    integration_warn_cfg = (
        integration_policy.get("classification", {}).get("WARN_if")
        if isinstance(integration_policy.get("classification"), dict)
        else {}
    )
    integration_checks = {
        "layer_boundary_violations_gt": layer_boundary_violations,
        "pack_conflicts_gt": pack_conflicts,
        "core_unlock_scope_widen_gt": core_unlock_scope_widen,
        "schema_fail_gt": schema_fail_count,
    }
    integration_reason_base = {
        "layer_boundary_violations_gt": "layer_boundary_violations",
        "pack_conflicts_gt": "pack_conflicts",
        "core_unlock_scope_widen_gt": "core_unlock_scope_widen",
        "schema_fail_gt": "schema_fail",
    }

    def _resolve_integration_threshold(value: Any) -> float:
        if isinstance(value, str):
            return float(integration_thresholds.get(value, 0) or 0)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    integration_fail_reasons: list[str] = []
    integration_warn_reasons: list[str] = []
    for key in ["layer_boundary_violations_gt", "pack_conflicts_gt", "core_unlock_scope_widen_gt", "schema_fail_gt"]:
        count_val = int(integration_checks.get(key, 0) or 0)
        base = integration_reason_base.get(key, key.replace("_gt", ""))
        if key in integration_fail_cfg and count_val > _resolve_integration_threshold(integration_fail_cfg.get(key)):
            integration_fail_reasons.append(f"{base}_fail")
            continue
        if key in integration_warn_cfg and count_val > _resolve_integration_threshold(integration_warn_cfg.get(key)):
            integration_warn_reasons.append(f"{base}_warn")

    if integration_fail_reasons:
        integration_classification = "FAIL"
    elif integration_warn_reasons:
        integration_classification = "WARN"
    else:
        integration_classification = "OK"

    integration_score = {"OK": 1.0, "WARN": 0.5, "FAIL": 0.0}[integration_classification]
    integration_reasons = sorted(set(integration_fail_reasons or integration_warn_reasons))

    integration_required = integration_cfg.get("required_signals")
    integration_required_list = [str(x) for x in integration_required if isinstance(x, str) and x.strip()] if isinstance(
        integration_required, list
    ) else []
    if integration_required_list:
        present_count = len(integration_required_list) if isinstance(integration_signals, dict) else 0
        integration_coverage = present_count / float(len(integration_required_list))
    else:
        integration_coverage = 0.0

    ai_ops_findings = _build_ai_ops_fit_findings(
        workspace_root=workspace_root,
        raw_ref=raw_ref,
        requirements={
            "context_pack_present": bool(context_pack_present),
            "provider_policy_pinned": bool(provider_policy_pinned),
            "secrets_redacted": bool(secrets_redacted),
        },
    )
    gh_ops_findings = _build_github_ops_release_findings(
        workspace_root=workspace_root,
        raw_ref=raw_ref,
        requirements=gh_requirements,
    )
    integration_findings = _build_integration_coherence_findings(
        workspace_root=workspace_root,
        raw_ref=raw_ref,
        signals_present=bool(integration_signals_present),
        thresholds=integration_thresholds,
        warn_cfg=integration_warn_cfg if isinstance(integration_warn_cfg, dict) else {},
        fail_cfg=integration_fail_cfg if isinstance(integration_fail_cfg, dict) else {},
        checks=integration_checks,
    )
    operability_findings = _build_operability_findings(
        workspace_root=workspace_root,
        raw_ref=raw_ref,
        required_map=required_map,
        thresholds=thresholds,
        warn_cfg=warn_cfg if isinstance(warn_cfg, dict) else {},
        fail_cfg=fail_cfg if isinstance(fail_cfg, dict) else {},
        values={},
        fail_reasons=fail_reasons,
        warn_reasons=warn_reasons,
        evidence_paths={
            "script_budget_report_path": sb_signal.get("report_path"),
            "doc_nav_report_path": doc_nav_signal.get("report_path"),
            "heartbeat_path": heartbeat_signal.get("heartbeat_path"),
            "integrity_snapshot_ref": integrity_snapshot_ref,
            "airrunner_jobs_index_path": jobs_signal.get("jobs_index_path"),
        },
    )
    # Eval-G: Context Health lens
    context_health_result = _compute_context_health_lens(workspace_root=workspace_root, lenses_policy=lenses_policy)
    context_health_status = str(context_health_result.get("status", "UNKNOWN"))
    context_health_score = float(context_health_result.get("score", 0.0))
    context_health_reasons = context_health_result.get("reasons", [])

    lens_dimension_map = _normalized_dimension_map(lenses_policy)
    lens_scores_map = {
        "trend_best_practice": {"status": trend_status, "score": round(float(coverage), 4)},
        "integrity_compat": {"status": integrity_lens_status, "score": round(float(integrity_score), 4)},
        "integration_coherence": {"status": integration_classification, "score": round(float(integration_score), 4)},
        "ai_ops_fit": {"status": ai_ops_status, "score": round(float(ai_ops_score), 4)},
        "github_ops_release": {"status": gh_status, "score": round(float(gh_score), 4)},
        "operability": {"status": operability_status, "score": round(float(operability_score), 4)},
        "context_health": {"status": context_health_status, "score": round(context_health_score, 4)},
    }
    maturity_doc = _build_maturity_document(
        workspace_root=workspace_root,
        lenses_policy=lenses_policy,
        mode="lenses",
        coverage=coverage,
        lens_scores=lens_scores_map,
        fallback_score=coverage,
    )
    maturity_tracking = maturity_doc.get("tracking") if isinstance(maturity_doc.get("tracking"), dict) else {}
    maturity_avg = _safe_unit_float(maturity_tracking.get("score"), 0.0)

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "report_only": bool(report_only),
        "integrity_snapshot_ref": str(integrity_snapshot_ref),
        "raw_ref": str(raw_ref),
        "bp_catalog_ref": str(Path(".cache") / "index" / "bp_catalog.v1.json"),
        "trend_catalog_ref": str(Path(".cache") / "index" / "trend_catalog.v1.json"),
        "scores": {"maturity_avg": round(maturity_avg, 4), "coverage": round(coverage, 4)},
        "inputs": {"controls": controls, "metrics": metrics, "bp_items": bp_items, "trend_items": trend_items},
        "lenses": {
            "trend_best_practice": {
                "dimension": lens_dimension_map.get("trend_best_practice", "A"),
                "status": trend_status,
                "score": round(float(coverage), 4),
                "coverage": round(float(coverage), 4),
                "notes": [],
                "findings": trend_findings,
            },
            "integrity_compat": {
                "dimension": lens_dimension_map.get("integrity_compat", "B"),
                "status": integrity_lens_status,
                "score": round(float(integrity_score), 4),
                "integrity_status": str(integrity_status or "FAIL"),
                "notes": [],
            },
            "integration_coherence": {
                "dimension": lens_dimension_map.get("integration_coherence", "F"),
                "status": integration_classification,
                "score": round(float(integration_score), 4),
                "classification": integration_classification,
                "coverage": round(float(integration_coverage), 4),
                "reasons": integration_reasons,
                "findings": integration_findings,
            },
            "ai_ops_fit": {
                "dimension": lens_dimension_map.get("ai_ops_fit", "C"),
                "status": ai_ops_status,
                "score": round(float(ai_ops_score), 4),
                "requirements": {
                    "context_pack_present": bool(context_pack_present),
                    "provider_policy_pinned": bool(provider_policy_pinned),
                    "secrets_redacted": bool(secrets_redacted),
                },
                "notes": [],
                "findings": ai_ops_findings,
            },
            "github_ops_release": {
                "dimension": lens_dimension_map.get("github_ops_release", "D"),
                "status": gh_status,
                "score": round(float(gh_score), 4),
                "coverage": round(float(gh_score), 4),
                "requirements": gh_requirements,
                "notes": gh_notes,
                "findings": gh_ops_findings,
            },
            "operability": {
                "dimension": lens_dimension_map.get("operability", "E"),
                "status": operability_status,
                "score": round(float(operability_score), 4),
                "classification": operability_classification,
                "coverage": round(float(operability_coverage), 4),
                "subscores": {
                    "simplicity": round(float(simplicity), 4),
                    "sustainability": round(float(sustainability), 4),
                    "continuity": round(float(continuity), 4),
                },
                "reasons": reasons,
                "findings": operability_findings,
            },
            "context_health": {
                "dimension": lens_dimension_map.get("context_health", "G"),
                "status": context_health_status,
                "score": round(context_health_score, 4),
                "components": context_health_result.get("components", {}),
                "reasons": context_health_reasons,
                "notes": [],
            },
        },
        "maturity_tracking": maturity_doc,
        "notes": sorted(set(notes)),
    }

    schema_path = core_root / "schemas" / "assessment-eval.schema.v1.json"
    if schema_path.exists():
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(payload)

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "out": str(eval_path),
            "report_only": report_only,
        }

    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "OK",
        "out": str(eval_path),
        "report_only": report_only,
    }
