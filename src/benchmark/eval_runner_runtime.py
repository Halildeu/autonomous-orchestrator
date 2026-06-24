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
from src.shared.utils import write_json_atomic

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

    # Component 7: Rule Relevance (0-20) — how many loaded rules were actually used
    rule_relevance_score = 20  # Default: no metrics yet
    metrics_path = workspace_root / ".cache" / "reports" / "context_session_metrics.v1.json"
    if metrics_path.exists():
        try:
            import json as _json2
            metrics = _json2.loads(metrics_path.read_text(encoding="utf-8"))
            applied = metrics.get("rules_applied", 0)
            total_loaded = metrics.get("rules_loaded", 1)
            if total_loaded > 0:
                rule_relevance_score = min(20, int((applied / total_loaded) * 20))
            if rule_relevance_score < 12:
                reasons.append(f"low_rule_relevance_{rule_relevance_score}/20")
        except Exception:
            pass
    components["rule_relevance"] = {"score": rule_relevance_score, "max": 20}

    # Component 8: Token Efficiency (0-20) — compiled context size vs limit
    efficiency_score = 20  # Default: efficient
    compiled_ctx_path = workspace_root / ".cache" / "reports" / "rule_packet.v1.json"
    if compiled_ctx_path.exists():
        try:
            ctx_size = compiled_ctx_path.stat().st_size
            max_bytes = 65536  # policy_context_orchestration max_context_pack_bytes
            ratio = ctx_size / max_bytes
            if ratio > 0.8:
                efficiency_score = 5
                reasons.append("context_pack_near_limit")
            elif ratio > 0.5:
                efficiency_score = 12
            else:
                efficiency_score = 20
        except Exception:
            pass
    components["token_efficiency"] = {"score": efficiency_score, "max": 20}

    # Component 9: Cache Hit Rate (0-20) — compilation cache effectiveness
    cache_score = 20  # Default: no data
    if metrics_path.exists():
        try:
            import json as _json3
            metrics = _json3.loads(metrics_path.read_text(encoding="utf-8"))
            hits = metrics.get("cache_hits", 0)
            misses = metrics.get("cache_misses", 0)
            total_cache = hits + misses
            if total_cache > 0:
                hit_rate = hits / total_cache
                cache_score = min(20, int(hit_rate * 20))
                if hit_rate < 0.5:
                    reasons.append(f"low_cache_hit_rate_{hit_rate:.2f}")
        except Exception:
            pass
    components["cache_hit_rate"] = {"score": cache_score, "max": 20}

    # Total score: sum of 9 components (0-180) → normalize to 0.0-1.0
    total = sum(c["score"] for c in components.values())
    normalized = total / 180.0

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
    from src.benchmark.eval_runner_runtime_run import run_eval_impl

    return run_eval_impl(workspace_root=workspace_root, dry_run=dry_run)
