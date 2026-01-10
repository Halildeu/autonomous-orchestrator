from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.integrity_utils import load_policy_integrity


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _write_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_policy_north_star_eval_lenses(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    defaults = {
        "version": "v1",
        "eval_lenses_enabled": ["trend", "integrity_compat", "ai_ops_fit", "github_ops_release", "operability"],
        "trend_best_practice": {"min_coverage_ok": 0.5, "min_coverage_warn": 0.2},
        "integrity_compat": {"min_score_ok": 1.0, "min_score_warn": 0.5},
        "ai_ops_fit": {
            "required_fields": ["context_pack_present", "provider_policy_pinned", "secrets_redacted"],
            "min_score_ok": 1.0,
            "min_score_warn": 0.5,
        },
        "github_ops_release": {
            "required_fields": [
                "github_ops_policy_present",
                "github_ops_network_default_off",
                "release_policy_present",
                "github_jobs_index_present",
                "release_manifest_present",
            ],
            "min_score_ok": 1.0,
            "min_score_warn": 0.5,
        },
        "operability": {
            "required_fields": [
                "script_budget_present",
                "doc_nav_present",
                "airunner_jobs_present",
                "pdca_cursor_present",
                "heartbeat_present",
                "work_intake_present",
                "integrity_present",
            ],
            "min_score_ok": 1.0,
            "min_score_warn": 0.5,
            "weights": {"simplicity": 0.34, "sustainability": 0.33, "continuity": 0.33},
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
        "thresholds": {
            "hard_exceeded_must_be": 0,
            "soft_target": 0,
            "soft_warn": 1,
            "placeholders_warn": 25,
            "placeholders_fail": 200,
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
            "airunner_jobs": True,
            "pdca_cursor": True,
            "airunner_heartbeat": True,
            "work_intake_noise": True,
            "integrity_pass_required": True,
        },
        "classification": {"FAIL_if": {}, "WARN_if": {}},
        "gap_rules": {},
    }
    ws_policy = workspace_root / "policies" / "policy_north_star_operability.v1.json"
    core_policy = core_root / "policies" / "policy_north_star_operability.v1.json"
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
    operability_cfg = (
        lenses_policy.get("operability") if isinstance(lenses_policy.get("operability"), dict) else {}
    )
    operability_required_fields = operability_cfg.get("required_fields")
    if not isinstance(operability_required_fields, list):
        operability_required_fields = [
            "script_budget_present",
            "doc_nav_present",
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
    jobs_signal = raw_signals.get("airunner_jobs") if isinstance(raw_signals.get("airunner_jobs"), dict) else {}
    pdca_signal = raw_signals.get("pdca_cursor") if isinstance(raw_signals.get("pdca_cursor"), dict) else {}
    heartbeat_signal = (
        raw_signals.get("airunner_heartbeat") if isinstance(raw_signals.get("airunner_heartbeat"), dict) else {}
    )
    intake_signal = raw_signals.get("work_intake_noise") if isinstance(raw_signals.get("work_intake_noise"), dict) else {}
    integrity_signal = raw_signals.get("integrity") if isinstance(raw_signals.get("integrity"), dict) else {}

    required_map = {
        "script_budget_present": isinstance(raw_signals.get("script_budget"), dict),
        "doc_nav_present": isinstance(raw_signals.get("doc_nav"), dict),
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
    jobs_stuck = int(jobs_signal.get("stuck", 0) or 0)
    jobs_fail = int(jobs_signal.get("fail", 0) or 0)
    pdca_stale = float(pdca_signal.get("stale_hours", 0.0) or 0.0)
    heartbeat_stale = int(heartbeat_signal.get("stale_seconds", 0) or 0)
    intake_new = int(intake_signal.get("new_items_24h", 0) or 0)
    suppressed = int(intake_signal.get("suppressed_24h", 0) or 0)
    integrity_status_signal = str(integrity_signal.get("status") or "")

    def _resolve_threshold(value: Any) -> float:
        if isinstance(value, str):
            return float(thresholds.get(value, 0) or 0)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []
    ordered_checks = [
        "hard_exceeded_gt",
        "soft_exceeded_gt",
        "integrity_fail",
        "jobs_stuck_gt",
        "jobs_fail_gt",
        "pdca_cursor_stale_hours_gt",
        "heartbeat_stale_seconds_gt",
        "placeholders_gt",
        "intake_new_items_per_day_gt",
        "suppressed_per_day_gt",
    ]
    for key in ordered_checks:
        if key in fail_cfg:
            if key == "integrity_fail" and bool(fail_cfg.get(key)) and integrity_status_signal == "FAIL":
                fail_reasons.append(key)
            elif key == "hard_exceeded_gt" and hard_exceeded > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "jobs_stuck_gt" and jobs_stuck > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "jobs_fail_gt" and jobs_fail > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "pdca_cursor_stale_hours_gt" and pdca_stale > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "heartbeat_stale_seconds_gt" and heartbeat_stale > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "placeholders_gt" and placeholders > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "intake_new_items_per_day_gt" and intake_new > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
            elif key == "suppressed_per_day_gt" and suppressed > _resolve_threshold(fail_cfg.get(key)):
                fail_reasons.append(key)
        if key in warn_cfg:
            if key == "hard_exceeded_gt" and hard_exceeded > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "jobs_stuck_gt" and jobs_stuck > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "jobs_fail_gt" and jobs_fail > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "pdca_cursor_stale_hours_gt" and pdca_stale > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "heartbeat_stale_seconds_gt" and heartbeat_stale > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "placeholders_gt" and placeholders > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "intake_new_items_per_day_gt" and intake_new > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "suppressed_per_day_gt" and suppressed > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)
            elif key == "soft_exceeded_gt" and soft_exceeded > _resolve_threshold(warn_cfg.get(key)):
                warn_reasons.append(key)

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
    intake_warn = float(thresholds.get("intake_new_items_per_day_warn", 0) or 0)
    intake_fail = float(thresholds.get("intake_new_items_per_day_fail", 0) or 0)
    suppressed_warn = float(thresholds.get("suppressed_per_day_warn", 0) or 0)
    sustainability = 1.0
    if placeholders > placeholders_fail or intake_new > intake_fail:
        sustainability = 0.0
    elif placeholders > placeholders_warn or intake_new > intake_warn or suppressed > suppressed_warn:
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
        or heartbeat_stale > heartbeat_fail
    ):
        continuity = 0.0
    elif (
        jobs_stuck > jobs_stuck_warn
        or jobs_fail > jobs_fail_warn
        or pdca_stale > pdca_warn
        or heartbeat_stale > heartbeat_warn
    ):
        continuity = 0.5

    min_operability_ok = float(operability_cfg.get("min_score_ok", 1.0) or 1.0)
    min_operability_warn = float(operability_cfg.get("min_score_warn", 0.5) or 0.5)
    operability_status = _lens_status(float(operability_score), min_operability_ok, min_operability_warn)

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
                "status": trend_status,
                "score": round(float(coverage), 4),
                "coverage": round(float(coverage), 4),
                "notes": [],
            },
            "integrity_compat": {
                "status": integrity_lens_status,
                "score": round(float(integrity_score), 4),
                "integrity_status": str(integrity_status or "FAIL"),
                "notes": [],
            },
            "ai_ops_fit": {
                "status": ai_ops_status,
                "score": round(float(ai_ops_score), 4),
                "requirements": {
                    "context_pack_present": bool(context_pack_present),
                    "provider_policy_pinned": bool(provider_policy_pinned),
                    "secrets_redacted": bool(secrets_redacted),
                },
                "notes": [],
            },
            "github_ops_release": {
                "status": gh_status,
                "score": round(float(gh_score), 4),
                "coverage": round(float(gh_score), 4),
                "requirements": gh_requirements,
                "notes": gh_notes,
            },
            "operability": {
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
            },
        },
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
