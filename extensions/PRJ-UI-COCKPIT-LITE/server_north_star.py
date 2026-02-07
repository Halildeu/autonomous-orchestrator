from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from server_utils import _read_json_file


def build_north_star_payload(
    *,
    repo_root: Path,
    ws_root: Path,
    wrap_file: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    eval_path = ws_root / ".cache" / "index" / "assessment_eval.v1.json"
    raw_path = ws_root / ".cache" / "index" / "assessment_raw.v1.json"
    gap_path = ws_root / ".cache" / "index" / "gap_register.v1.json"
    trend_catalog_path = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
    bp_catalog_path = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
    north_star_catalog_path = ws_root / ".cache" / "index" / "north_star_catalog.v1.json"
    reference_matrix_path = ws_root / ".cache" / "index" / "reference_matrix.v1.json"
    assessment_matrix_path = ws_root / ".cache" / "index" / "assessment_matrix.v1.json"
    gap_matrix_path = ws_root / ".cache" / "index" / "gap_matrix.v1.json"
    scorecard_path = ws_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
    eval_payload = wrap_file(eval_path)
    raw_payload = wrap_file(raw_path)
    gap_payload = wrap_file(gap_path)
    trend_catalog_payload = wrap_file(trend_catalog_path)
    bp_catalog_payload = wrap_file(bp_catalog_path)
    north_star_catalog_payload = wrap_file(north_star_catalog_path)
    reference_matrix_payload = wrap_file(reference_matrix_path)
    assessment_matrix_payload = wrap_file(assessment_matrix_path)
    gap_matrix_payload = wrap_file(gap_matrix_path)
    scorecard_payload = wrap_file(scorecard_path)

    eval_data = eval_payload.get("data") if isinstance(eval_payload, dict) else {}
    raw_data = raw_payload.get("data") if isinstance(raw_payload, dict) else {}
    gap_data = gap_payload.get("data") if isinstance(gap_payload, dict) else {}
    lenses = eval_data.get("lenses") if isinstance(eval_data, dict) else {}
    gaps = gap_data.get("gaps") if isinstance(gap_data, dict) else []
    gap_list = gaps if isinstance(gaps, list) else []

    # Surface “capability vs expected” (monitoring) so UI can show:
    # enabled_effective / auto_mode_enabled_effective (capability)
    # heartbeat_expectation_mode (monitoring/expected)
    raw_signals = raw_data.get("signals") if isinstance(raw_data, dict) and isinstance(raw_data.get("signals"), dict) else {}
    airunner_state = raw_signals.get("airunner_state") if isinstance(raw_signals.get("airunner_state"), dict) else {}
    enabled_effective = (
        bool(airunner_state.get("enabled_effective"))
        if isinstance(airunner_state, dict) and "enabled_effective" in airunner_state
        else None
    )
    auto_mode_enabled_effective = (
        bool(airunner_state.get("auto_mode_enabled_effective"))
        if isinstance(airunner_state, dict) and "auto_mode_enabled_effective" in airunner_state
        else None
    )
    active_hours_is_now = None
    if isinstance(airunner_state, dict) and "active_hours_is_now" in airunner_state:
        active_hours_value = airunner_state.get("active_hours_is_now")
        active_hours_is_now = active_hours_value if isinstance(active_hours_value, bool) else None
    heartbeat_stale_seconds = None
    if isinstance(airunner_state, dict) and "heartbeat_stale_seconds" in airunner_state:
        try:
            heartbeat_stale_seconds = int(airunner_state.get("heartbeat_stale_seconds") or 0)
        except Exception:
            heartbeat_stale_seconds = None

    heartbeat_expectation_mode = None
    mode_source = "default"
    override_path = ws_root / ".cache" / "policy_overrides" / "policy_north_star_operability.override.v1.json"
    override_obj, override_exists, override_valid = _read_json_file(override_path)
    if override_exists and override_valid and isinstance(override_obj, dict):
        heartbeat_expectation_mode = override_obj.get("heartbeat_expectation_mode")
        if heartbeat_expectation_mode:
            mode_source = "override"
    policy_path = repo_root / "policies" / "policy_north_star_operability.v1.json"
    policy_obj, policy_exists, policy_valid = _read_json_file(policy_path)
    thresholds = (
        policy_obj.get("thresholds")
        if policy_exists and policy_valid and isinstance(policy_obj, dict) and isinstance(policy_obj.get("thresholds"), dict)
        else {}
    )
    override_thresholds = (
        override_obj.get("thresholds")
        if override_exists and override_valid and isinstance(override_obj, dict) and isinstance(override_obj.get("thresholds"), dict)
        else {}
    )
    if override_thresholds:
        merged = dict(thresholds)
        merged.update(override_thresholds)
        thresholds = merged

    if not heartbeat_expectation_mode and policy_exists and policy_valid and isinstance(policy_obj, dict):
        heartbeat_expectation_mode = policy_obj.get("heartbeat_expectation_mode")
    heartbeat_expectation_mode = str(heartbeat_expectation_mode or "ALWAYS").strip().upper()
    if heartbeat_expectation_mode not in {"ALWAYS", "ACTIVE_HOURS", "NONE"}:
        heartbeat_expectation_mode = "ALWAYS"

    heartbeat_warn_seconds = None
    heartbeat_fail_seconds = None
    if isinstance(thresholds, dict):
        try:
            heartbeat_warn_seconds = int(thresholds.get("heartbeat_stale_seconds_warn"))  # type: ignore[arg-type]
        except Exception:
            heartbeat_warn_seconds = None
        try:
            heartbeat_fail_seconds = int(thresholds.get("heartbeat_stale_seconds_fail"))  # type: ignore[arg-type]
        except Exception:
            heartbeat_fail_seconds = None

    heartbeat_capability = bool(enabled_effective) or bool(auto_mode_enabled_effective)
    if heartbeat_expectation_mode == "NONE":
        heartbeat_expected_now = False
    elif heartbeat_expectation_mode == "ACTIVE_HOURS":
        active_hours_is_now_bool = bool(active_hours_is_now) if isinstance(active_hours_is_now, bool) else True
        heartbeat_expected_now = heartbeat_capability and active_hours_is_now_bool
    else:
        heartbeat_expected_now = heartbeat_capability

    heartbeat_stale_level = "UNKNOWN"
    if not heartbeat_expected_now:
        heartbeat_stale_level = "NOT_EXPECTED"
    elif heartbeat_stale_seconds is None:
        heartbeat_stale_level = "UNKNOWN"
    else:
        if heartbeat_fail_seconds is not None and heartbeat_stale_seconds >= heartbeat_fail_seconds:
            heartbeat_stale_level = "FAIL"
        elif heartbeat_warn_seconds is not None and heartbeat_stale_seconds >= heartbeat_warn_seconds:
            heartbeat_stale_level = "WARN"
        else:
            heartbeat_stale_level = "OK"

    runner_meta = {
        "auto_mode_enabled_effective": auto_mode_enabled_effective,
        "enabled_effective": enabled_effective,
        "active_hours_is_now": active_hours_is_now,
        "heartbeat_expectation_mode": heartbeat_expectation_mode,
        "heartbeat_expectation_source": mode_source,
        "heartbeat_expected_now": bool(heartbeat_expected_now),
        "heartbeat_stale_seconds": heartbeat_stale_seconds,
        "heartbeat_stale_level": heartbeat_stale_level,
        "heartbeat_stale_warn_seconds": heartbeat_warn_seconds,
        "heartbeat_stale_fail_seconds": heartbeat_fail_seconds,
    }

    lens_summary: dict[str, Any] = {}
    if isinstance(lenses, dict):
        for name in sorted(lenses.keys()):
            lens = lenses.get(name)
            if not isinstance(lens, dict):
                continue
            reqs = lens.get("requirements")
            req_list = reqs if isinstance(reqs, list) else []
            req_ok = 0
            for req in req_list:
                if isinstance(req, dict) and str(req.get("status") or "").upper() == "OK":
                    req_ok += 1
            lens_summary[name] = {
                "status": str(lens.get("status") or ""),
                "score": lens.get("score"),
                "coverage": lens.get("coverage"),
                "requirements_total": len(req_list),
                "requirements_ok": req_ok,
            }

    counts_sev: dict[str, int] = {}
    counts_risk: dict[str, int] = {}
    counts_effort: dict[str, int] = {}
    for gap in gap_list:
        if not isinstance(gap, dict):
            continue
        sev = str(gap.get("severity") or "").lower()
        risk = str(gap.get("risk_class") or "").lower()
        effort = str(gap.get("effort") or "").lower()
        if sev:
            counts_sev[sev] = counts_sev.get(sev, 0) + 1
        if risk:
            counts_risk[risk] = counts_risk.get(risk, 0) + 1
        if effort:
            counts_effort[effort] = counts_effort.get(effort, 0) + 1

    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    top_gaps = [gap for gap in gap_list if isinstance(gap, dict)]
    top_gaps.sort(
        key=lambda g: (sev_rank.get(str(g.get("severity") or "").lower(), 9), str(g.get("id") or ""))
    )
    top_gaps = [
        {
            "id": str(g.get("id") or ""),
            "control_id": str(g.get("control_id") or ""),
            "severity": str(g.get("severity") or ""),
            "risk_class": str(g.get("risk_class") or ""),
            "effort": str(g.get("effort") or ""),
            "status": str(g.get("status") or ""),
        }
        for g in top_gaps[:12]
    ]

    summary = {
        "status": str(eval_data.get("status") or ""),
        "generated_at": str(eval_data.get("generated_at") or ""),
        "scores": eval_data.get("scores") if isinstance(eval_data, dict) else {},
        "gap_count": len(gap_list),
        "lens_count": len(lens_summary),
        "gap_by_severity": {k: counts_sev[k] for k in sorted(counts_sev)},
        "gap_by_risk_class": {k: counts_risk[k] for k in sorted(counts_risk)},
        "gap_by_effort": {k: counts_effort[k] for k in sorted(counts_effort)},
    }
    return {
        "summary": summary,
        "runner_meta": runner_meta,
        "lenses": lens_summary,
        "top_gaps": top_gaps,
        "assessment_eval": eval_payload,
        "trend_catalog": trend_catalog_payload,
        "bp_catalog": bp_catalog_payload,
        "north_star_catalog": north_star_catalog_payload,
        "reference_matrix": reference_matrix_payload,
        "assessment_matrix": assessment_matrix_payload,
        "gap_matrix": gap_matrix_payload,
        "gap_register": {
            "path": gap_payload.get("path"),
            "exists": gap_payload.get("exists"),
            "json_valid": gap_payload.get("json_valid"),
            "gap_count": len(gap_list),
        },
        "scorecard": scorecard_payload,
    }
