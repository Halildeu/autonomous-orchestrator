from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.work_intake_job_sources import (
    _apply_deploy_job_cooldown,
    _apply_github_ops_cooldown,
    _apply_job_status_cooldown,
    _load_doc_nav_sources,
    _load_deploy_job_sources,
    _load_github_ops_sources,
    _load_job_status_sources,
    _load_time_sink_sources,
)
from src.ops.work_intake_release_sources import (
    _find_repo_root,
    _load_integrity_sources,
    _load_release_sources,
)
from src.ops.work_intake_helpers import (
    _load_exec_ticket_applied_ids,
    _normalize_evidence,
    _suggested_extensions,
)
from src.ops.work_item_state import FINAL_STATES, load_state_map
from src.ops.work_intake_autopilot import (
    _autopilot_labels,
    _load_autopilot_policy,
    _load_autopilot_selection,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_band(value: str) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "xs": "low",
        "s": "low",
        "low": "low",
        "m": "medium",
        "med": "medium",
        "medium": "medium",
        "l": "high",
        "high": "high",
    }
    return mapping.get(raw, raw)


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _load_policy(*, core_root: Path, workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    ws_policy = workspace_root / "policies" / "policy_work_intake.v2.json"
    core_policy = core_root / "policies" / "policy_work_intake.v2.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if path.exists():
        try:
            obj = _load_json(path)
            if isinstance(obj, dict):
                return obj, notes
        except Exception:
            notes.append("policy_invalid")
    notes.append("policy_missing")
    return {}, notes


def _load_integration_coherence_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_north_star_integration_coherence.v1.json"
    core_policy = core_root / "policies" / "policy_north_star_integration_coherence.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {}
    try:
        obj = _load_json(path)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _parse_gap_rule(rule: str) -> tuple[str, list[str]]:
    if not isinstance(rule, str) or not rule.strip():
        return ("", [])
    parts = rule.strip().split(":", 1)
    bucket = parts[0].strip()
    tag = parts[1].strip() if len(parts) == 2 else ""
    tags = [tag.lower()] if tag else []
    return (bucket, tags)


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v2",
        "enabled": True,
        "plan_policy": "optional",
        "bucket_order": ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"],
        "bucket_rules": [
            {
                "id": "doc_nav_critical",
                "source_type": "DOC_NAV",
                "when": {"critical_nav_gaps_gt": 0},
                "bucket": "INCIDENT",
                "severity": "S1",
                "priority": "P1",
            },
            {
                "id": "pdca_regression_high",
                "source_type": "PDCA_REGRESSION",
                "when": {"regression_severity_gte": "high"},
                "bucket": "INCIDENT",
                "severity": "S1",
                "priority": "P1",
            },
            {
                "id": "script_budget_hard",
                "source_type": "SCRIPT_BUDGET",
                "when": {"hard_exceeded_gt": 0},
                "bucket": "INCIDENT",
                "severity": "S1",
                "priority": "P1",
            },
            {
                "id": "integrity_fail",
                "source_type": "INTEGRITY",
                "when": {"integrity_status_in": ["FAIL"]},
                "bucket": "INCIDENT",
                "severity": "S1",
                "priority": "P1",
            },
            {
                "id": "manual_request_core_change",
                "source_type": "MANUAL_REQUEST",
                "when": {"manual_request_requires_core_change": True},
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
                "tags": ["plan_only"],
            },
            {
                "id": "manual_request_strategy",
                "source_type": "MANUAL_REQUEST",
                "when": {"manual_request_kind_in": ["strategy", "multi-quarter"]},
                "bucket": "ROADMAP",
                "severity": "S2",
                "priority": "P2",
            },
            {
                "id": "manual_request_context_router_doc_only",
                "source_type": "MANUAL_REQUEST",
                "when": {
                    "manual_request_kind_in": ["context-router"],
                    "manual_request_impact_scope_in": ["doc-only"],
                },
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "manual_request_context_router_project",
                "source_type": "MANUAL_REQUEST",
                "when": {
                    "manual_request_kind_in": ["context-router"],
                    "manual_request_impact_scope_in": ["unknown", "platform", "core"],
                },
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
                "tags": ["plan_only"],
            },
            {
                "id": "manual_request_project",
                "source_type": "MANUAL_REQUEST",
                "when": {"manual_request_kind_in": ["feature", "refactor", "new_project"]},
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
            },
            {
                "id": "manual_request_ticket",
                "source_type": "MANUAL_REQUEST",
                "when": {"manual_request_kind_in": ["support", "question", "minor_fix", "doc-fix", "note"]},
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "doc_nav_broken_refs",
                "source_type": "DOC_NAV",
                "when": {"broken_refs_gt": 0},
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "gap_effort_small",
                "source_type": "GAP",
                "when": {"effort_in": ["XS", "S", "LOW"]},
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "gap_low_risk",
                "source_type": "GAP",
                "when": {"risk_in": ["LOW"]},
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "gap_severity_s3",
                "source_type": "GAP",
                "when": {"severity_in": ["S3"]},
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "script_budget_soft_docs",
                "source_type": "SCRIPT_BUDGET",
                "when": {
                    "hard_exceeded_eq": 0,
                    "soft_only": True,
                    "path_prefix_in": ["docs/", "tests/", "test/", "ci/", "scripts/", "tools/"],
                },
                "bucket": "TICKET",
                "severity": "S3",
                "priority": "P3",
            },
            {
                "id": "script_budget_soft_ops",
                "source_type": "SCRIPT_BUDGET",
                "when": {
                    "hard_exceeded_eq": 0,
                    "soft_only": True,
                    "path_prefix_in": ["src/ops/", "src/orchestrator/"],
                },
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
                "tags": ["M0"],
            },
            {
                "id": "script_budget_soft_default",
                "source_type": "SCRIPT_BUDGET",
                "when": {"hard_exceeded_eq": 0, "soft_only": True},
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
                "tags": ["M0"],
            },
            {
                "id": "gap_medium_high_risk",
                "source_type": "GAP",
                "when": {"severity_in": ["S1", "S2"], "risk_in": ["MEDIUM", "HIGH"]},
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
            },
            {
                "id": "gap_medium_high_effort",
                "source_type": "GAP",
                "when": {"severity_in": ["S1", "S2"], "effort_in": ["M", "L", "MEDIUM", "HIGH"]},
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
            },
            {
                "id": "gap_default_project",
                "source_type": "GAP",
                "bucket": "PROJECT",
                "severity": "S2",
                "priority": "P2",
            },
        ],
        "default_rule": {"bucket": "TICKET", "severity": "S3", "priority": "P3"},
        "dedupe": {"strategy": "stable_sha256", "template": "source_type+source_ref+bucket"},
        "sla_hints": {
            "INCIDENT": "4h",
            "TICKET": "5d",
            "PROJECT": "sprint",
            "ROADMAP": "quarter",
        },
    }


def _severity_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(_normalize_band(value), 1)


def _risk_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(_normalize_band(value), 1)


def _effort_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(_normalize_band(value), 1)


def _severity_level_rank(value: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(str(value), 4)


def _severity_level_from_band(value: str) -> str:
    band = _normalize_band(value)
    return {"low": "S3", "medium": "S2", "high": "S1"}.get(band, "S3")


def _priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(value, 9)


def _apply_rule(source: dict[str, Any], rule: dict[str, Any]) -> bool:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    if "critical_nav_gaps_gt" in when:
        gap_val = int(source.get("critical_nav_gaps", 0))
        if gap_val <= int(when.get("critical_nav_gaps_gt", 0)):
            return False
    if "broken_refs_gt" in when:
        broken_val = int(source.get("broken_refs", 0))
        if broken_val <= int(when.get("broken_refs_gt", 0)):
            return False
    if "regression_severity_gte" in when:
        req = str(when.get("regression_severity_gte"))
        cur = str(source.get("regression_severity", "medium"))
        if _severity_rank(cur) < _severity_rank(req):
            return False
    if "budget_status_in" in when:
        status = str(source.get("budget_status", ""))
        allowed = [str(x) for x in when.get("budget_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "integrity_status_in" in when:
        status = str(source.get("integrity_status", ""))
        allowed = [str(x) for x in when.get("integrity_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "hard_exceeded_gt" in when:
        hard_count = int(source.get("hard_exceeded", 0))
        if hard_count <= int(when.get("hard_exceeded_gt", 0)):
            return False
    if "hard_exceeded_eq" in when:
        hard_count = int(source.get("hard_exceeded", 0))
        if hard_count != int(when.get("hard_exceeded_eq", 0)):
            return False
    if "soft_only" in when:
        required = bool(when.get("soft_only"))
        if bool(source.get("soft_only", False)) != required:
            return False
    if "path_prefix_in" in when:
        path = str(source.get("path", ""))
        prefixes = [str(x) for x in when.get("path_prefix_in", []) if isinstance(x, str)]
        if not any(path.startswith(pref) for pref in prefixes):
            return False
    if "manual_request_kind_in" in when:
        kind = str(source.get("manual_request_kind", ""))
        allowed = [str(x) for x in when.get("manual_request_kind_in", []) if isinstance(x, str)]
        if kind not in allowed:
            return False
    if "manual_request_kind_eq" in when:
        kind = str(source.get("manual_request_kind", ""))
        if kind != str(when.get("manual_request_kind_eq", "")):
            return False
    if "manual_request_impact_scope_in" in when:
        scope = str(source.get("manual_request_impact_scope", "unknown"))
        allowed = [str(x) for x in when.get("manual_request_impact_scope_in", []) if isinstance(x, str)]
        if scope not in allowed:
            return False
    if "manual_request_requires_core_change" in when:
        required = bool(when.get("manual_request_requires_core_change"))
        if bool(source.get("manual_request_requires_core_change", False)) != required:
            return False
    if "release_signal_in" in when:
        signal = str(source.get("release_signal", ""))
        allowed = [str(x) for x in when.get("release_signal_in", []) if isinstance(x, str)]
        if signal not in allowed:
            return False
    if "release_channel_in" in when:
        channel = str(source.get("release_channel", ""))
        allowed = [str(x) for x in when.get("release_channel_in", []) if isinstance(x, str)]
        if channel not in allowed:
            return False
    if "release_status_in" in when:
        status = str(source.get("release_status", ""))
        allowed = [str(x) for x in when.get("release_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "release_dirty_tree_eq" in when:
        required = bool(when.get("release_dirty_tree_eq"))
        if bool(source.get("release_dirty_tree", False)) != required:
            return False
    if "release_unpushed_commits_gt" in when:
        count = int(source.get("release_unpushed_commits", 0))
        if count <= int(when.get("release_unpushed_commits_gt", 0)):
            return False
    if "release_publish_blocked_eq" in when:
        required = bool(when.get("release_publish_blocked_eq"))
        if bool(source.get("release_publish_blocked", False)) != required:
            return False
    if "release_plan_present_eq" in when:
        required = bool(when.get("release_plan_present_eq"))
        if bool(source.get("release_plan_present", False)) != required:
            return False
    if "github_ops_signal_in" in when:
        signal = str(source.get("github_ops_signal", ""))
        allowed = [str(x) for x in when.get("github_ops_signal_in", []) if isinstance(x, str)]
        if signal not in allowed:
            return False
    if "github_ops_job_status_in" in when:
        status = str(source.get("github_ops_job_status", ""))
        allowed = [str(x) for x in when.get("github_ops_job_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "github_ops_job_failure_class_in" in when:
        failure_class = str(source.get("github_ops_job_failure_class", ""))
        allowed = [str(x) for x in when.get("github_ops_job_failure_class_in", []) if isinstance(x, str)]
        if failure_class not in allowed:
            return False
    if "github_ops_job_skip_reason_in" in when:
        reason = str(source.get("github_ops_job_skip_reason", ""))
        allowed = [str(x) for x in when.get("github_ops_job_skip_reason_in", []) if isinstance(x, str)]
        if reason not in allowed:
            return False
    if "job_status_in" in when:
        status = str(source.get("job_status", ""))
        allowed = [str(x) for x in when.get("job_status_in", []) if isinstance(x, str)]
        if status not in allowed:
            return False
    if "job_type_in" in when:
        job_type = str(source.get("job_type", ""))
        allowed = [str(x) for x in when.get("job_type_in", []) if isinstance(x, str)]
        if job_type not in allowed:
            return False
    if "job_failure_class_in" in when:
        failure_class = str(source.get("job_failure_class", ""))
        allowed = [str(x) for x in when.get("job_failure_class_in", []) if isinstance(x, str)]
        if failure_class not in allowed:
            return False
    if "job_skip_reason_in" in when:
        reason = str(source.get("job_skip_reason", ""))
        allowed = [str(x) for x in when.get("job_skip_reason_in", []) if isinstance(x, str)]
        if reason not in allowed:
            return False
    if "time_sink_escalate_eq" in when:
        required = bool(when.get("time_sink_escalate_eq"))
        if bool(source.get("time_sink_escalate", False)) != required:
            return False
    if "time_sink_over_threshold_eq" in when:
        required = bool(when.get("time_sink_over_threshold_eq"))
        if bool(source.get("time_sink_over_threshold", False)) != required:
            return False
    if "time_sink_breach_count_gte" in when:
        count = int(source.get("time_sink_breach_count", 0))
        if count < int(when.get("time_sink_breach_count_gte", 0)):
            return False
    if "time_sink_p95_ms_gte" in when:
        cur = int(source.get("time_sink_p95_ms", 0))
        if cur < int(when.get("time_sink_p95_ms_gte", 0)):
            return False
    if "lens_id_in" in when:
        lens_id = str(source.get("lens_id", ""))
        allowed = [str(x) for x in when.get("lens_id_in", []) if isinstance(x, str)]
        if lens_id not in allowed:
            return False
    if "lens_reason_in" in when:
        reason = str(source.get("lens_reason", ""))
        allowed = [str(x) for x in when.get("lens_reason_in", []) if isinstance(x, str)]
        if reason not in allowed:
            return False
    if "risk_in" in when:
        risk = _normalize_band(source.get("risk", ""))
        allowed = {_normalize_band(str(x)) for x in when.get("risk_in", []) if isinstance(x, str)}
        if risk not in allowed:
            return False
    if "risk_gte" in when:
        req = _normalize_band(str(when.get("risk_gte", "medium")))
        cur = _normalize_band(source.get("risk", "medium"))
        if _risk_rank(cur) < _risk_rank(req):
            return False
    if "effort_in" in when:
        effort = _normalize_band(source.get("effort", "medium"))
        allowed = {_normalize_band(str(x)) for x in when.get("effort_in", []) if isinstance(x, str)}
        if effort not in allowed:
            return False
    if "effort_gte" in when:
        req = _normalize_band(str(when.get("effort_gte", "medium")))
        cur = _normalize_band(str(source.get("effort", "medium")))
        if _effort_rank(cur) < _effort_rank(req):
            return False
    if "severity_in" in when:
        sev = str(source.get("severity_level") or source.get("severity") or "")
        allowed = [str(x) for x in when.get("severity_in", []) if isinstance(x, str)]
        if sev not in allowed:
            return False
    if "severity_gte" in when:
        req = str(when.get("severity_gte", "S3"))
        cur = str(source.get("severity_level") or source.get("severity") or "S3")
        if _severity_level_rank(cur) > _severity_level_rank(req):
            return False
    return True


def _classify_source(source: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    rules = policy.get("bucket_rules") if isinstance(policy.get("bucket_rules"), list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("source_type", "")) != str(source.get("source_type", "")):
            continue
        if not _apply_rule(source, rule):
            continue
        return rule
    default_rule = policy.get("default_rule") if isinstance(policy.get("default_rule"), dict) else {}
    return default_rule


def _intake_id(source_type: str, source_ref: str, bucket: str) -> str:
    return "INTAKE-" + _hash_text(f"{source_type}|{source_ref}|{bucket}")


def _ensure_script_budget_report(core_root: Path, workspace_root: Path, notes: list[str]) -> Path | None:
    ws_report = workspace_root / ".cache" / "script_budget" / "report.json"
    if ws_report.exists():
        return ws_report
    core_report = core_root / ".cache" / "script_budget" / "report.json"
    if not core_report.exists():
        notes.append("script_budget_missing")
        return None
    ws_report.parent.mkdir(parents=True, exist_ok=True)
    ws_report.write_text(core_report.read_text(encoding="utf-8"), encoding="utf-8")
    return ws_report


def _load_gap_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if not gap_path.exists():
        notes.append("gap_register_missing")
        return []
    try:
        obj = _load_json(gap_path)
    except Exception:
        notes.append("gap_register_invalid")
        return []
    gaps = obj.get("gaps") if isinstance(obj, dict) else None
    if not isinstance(gaps, list):
        notes.append("gap_register_empty")
        return []
    sources: list[dict[str, Any]] = []
    for gap in sorted([g for g in gaps if isinstance(g, dict)], key=lambda g: str(g.get("id") or "")):
        gap_id = gap.get("id") if isinstance(gap.get("id"), str) else ""
        if not gap_id:
            continue
        control_id = gap.get("control_id") if isinstance(gap.get("control_id"), str) else ""
        metric_id = gap.get("metric_id") if isinstance(gap.get("metric_id"), str) else ""
        effort = gap.get("effort") if isinstance(gap.get("effort"), str) else "medium"
        risk = gap.get("risk_class") if isinstance(gap.get("risk_class"), str) else "medium"
        severity_band = gap.get("severity") if isinstance(gap.get("severity"), str) else "medium"
        severity_level = _severity_level_from_band(severity_band)
        override_bucket = ""
        override_tags: list[str] = []
        title = f"Gap: {gap_id}"
        if control_id:
            title = f"Control gap: {control_id}"
        elif metric_id:
            title = f"Metric gap: {metric_id}"
        evidence = [str(Path(".cache") / "index" / "gap_register.v1.json")]
        extra = gap.get("evidence_pointers") if isinstance(gap.get("evidence_pointers"), list) else []
        for p in extra:
            if isinstance(p, str):
                evidence.append(p)
        sources.append(
            {
                "source_type": "GAP",
                "source_ref": gap_id,
                "title": title,
                "effort": effort,
                "risk": risk,
                "severity_level": severity_level,
                "override_bucket": override_bucket,
                "override_tags": override_tags,
                "evidence_paths": evidence,
            }
        )
    return sources


def _load_regression_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    reg_path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    if not reg_path.exists():
        notes.append("regression_index_missing")
        return []
    try:
        obj = _load_json(reg_path)
    except Exception:
        notes.append("regression_index_invalid")
        return []
    regressions = obj.get("regressions") if isinstance(obj, dict) else None
    if not isinstance(regressions, list):
        return []
    pdca_path = workspace_root / ".cache" / "reports" / "pdca_recheck_report.v1.json"
    sources: list[dict[str, Any]] = []
    for reg in sorted([r for r in regressions if isinstance(r, dict)], key=lambda r: str(r.get("gap_id") or "")):
        gap_id = reg.get("gap_id") if isinstance(reg.get("gap_id"), str) else ""
        if not gap_id:
            continue
        severity = reg.get("severity") if isinstance(reg.get("severity"), str) else "medium"
        evidence = [str(Path(".cache") / "index" / "regression_index.v1.json")]
        if pdca_path.exists():
            evidence.append(str(Path(".cache") / "reports" / "pdca_recheck_report.v1.json"))
        sources.append(
            {
                "source_type": "PDCA_REGRESSION",
                "source_ref": gap_id,
                "title": f"Regression: {gap_id}",
                "regression_severity": severity,
                "evidence_paths": evidence,
            }
        )
    return sources


def _load_script_budget_sources(core_root: Path, workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    report_path = _ensure_script_budget_report(core_root, workspace_root, notes)
    if report_path is None or not report_path.exists():
        return []
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("script_budget_invalid")
        return []
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = str(status) if isinstance(status, str) else ""
    entries: list[dict[str, Any]] = []
    exceeded_soft = obj.get("exceeded_soft") if isinstance(obj.get("exceeded_soft"), list) else []
    exceeded_hard = obj.get("exceeded_hard") if isinstance(obj.get("exceeded_hard"), list) else []
    hard_count = len([e for e in exceeded_hard if isinstance(e, dict)])
    soft_count = len([e for e in exceeded_soft if isinstance(e, dict)])
    soft_only = hard_count == 0
    for entry in exceeded_hard + exceeded_soft:
        if isinstance(entry, dict):
            entries.append(entry)
    sources: list[dict[str, Any]] = []
    evidence = [str(Path(".cache") / "script_budget" / "report.json")]
    if entries:
        for entry in sorted(entries, key=lambda e: str(e.get("path") or "")):
            path = entry.get("path") if isinstance(entry.get("path"), str) else ""
            if not path:
                continue
            sources.append(
                {
                    "source_type": "SCRIPT_BUDGET",
                    "source_ref": path,
                    "path": path,
                    "title": f"Script budget warn: {path}",
                    "budget_status": status_str,
                    "hard_exceeded": hard_count,
                    "soft_only": soft_only,
                    "evidence_paths": evidence,
                }
            )
    elif status_str in {"WARN", "FAIL"}:
        sources.append(
            {
                "source_type": "SCRIPT_BUDGET",
                "source_ref": f"script_budget:{status_str}",
                "title": "Script budget warning",
                "budget_status": status_str,
                "hard_exceeded": hard_count,
                "soft_only": soft_only,
                "evidence_paths": evidence,
            }
        )
    return sources


def _load_context_router_overrides(workspace_root: Path, notes: list[str]) -> dict[str, dict[str, Any]]:
    report_path = workspace_root / ".cache" / "reports" / "context_pack_router_result.v1.json"
    if not report_path.exists():
        notes.append("context_router_result_missing")
        return {}
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("context_router_result_invalid")
        return {}
    request_id = obj.get("request_id") if isinstance(obj, dict) else None
    bucket = obj.get("bucket") if isinstance(obj, dict) else None
    if not (isinstance(request_id, str) and request_id and isinstance(bucket, str) and bucket):
        notes.append("context_router_result_incomplete")
        return {}
    severity = obj.get("severity") if isinstance(obj, dict) else None
    priority = obj.get("priority") if isinstance(obj, dict) else None
    evidence = [str(Path(".cache") / "reports" / "context_pack_router_result.v1.json")]
    return {
        request_id: {
            "override_bucket": bucket,
            "override_severity": severity if isinstance(severity, str) else None,
            "override_priority": priority if isinstance(priority, str) else None,
            "override_evidence": evidence,
        }
    }


def _load_manual_request_sources(
    workspace_root: Path,
    notes: list[str],
    overrides: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    manual_dir = workspace_root / ".cache" / "index" / "manual_requests"
    if not manual_dir.exists():
        notes.append("manual_requests_missing")
        return []
    paths = sorted([p for p in manual_dir.glob("*.v1.json") if p.is_file()], key=lambda p: p.as_posix())
    if not paths:
        notes.append("manual_requests_empty")
        return []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        try:
            obj = _load_json(path)
        except Exception:
            notes.append("manual_request_invalid")
            continue
        if not isinstance(obj, dict):
            notes.append("manual_request_invalid")
            continue
        request_id = obj.get("request_id") if isinstance(obj.get("request_id"), str) else path.stem
        if not request_id or request_id in seen:
            continue
        seen.add(request_id)
        kind = obj.get("kind") if isinstance(obj.get("kind"), str) else "unspecified"
        impact_scope = obj.get("impact_scope") if isinstance(obj.get("impact_scope"), str) else "workspace-only"
        allowed_scopes = {"doc-only", "workspace-only", "core-change", "external-change"}
        if impact_scope not in allowed_scopes:
            impact_scope = "external-change"
        artifact_type = obj.get("artifact_type") if isinstance(obj.get("artifact_type"), str) else "request"
        domain = obj.get("domain") if isinstance(obj.get("domain"), str) else "general"
        created_at = obj.get("created_at") if isinstance(obj.get("created_at"), str) else ""
        title = f"Manual request: {artifact_type} / {domain}"
        constraints = obj.get("constraints") if isinstance(obj.get("constraints"), dict) else {}
        requires_core_change = bool(obj.get("requires_core_change", False))
        if not requires_core_change:
            requires_core_change = bool(constraints.get("requires_core_change", False))
        if str(constraints.get("layer", "")).strip() in {"L0", "L1"}:
            requires_core_change = True

        evidence = []
        rel_request = _rel_to_workspace(path, workspace_root)
        if rel_request:
            evidence.append(rel_request)

        attachments = obj.get("attachments") if isinstance(obj.get("attachments"), list) else []
        for att in attachments:
            if not isinstance(att, dict):
                continue
            kind_val = att.get("kind")
            value = att.get("value")
            if kind_val != "path" or not isinstance(value, str):
                continue
            p = (workspace_root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
            rel = _rel_to_workspace(p, workspace_root)
            if rel:
                evidence.append(rel)

        source: dict[str, Any] = {
            "source_type": "MANUAL_REQUEST",
            "source_ref": request_id,
            "title": title,
            "manual_request_kind": kind,
            "manual_request_impact_scope": impact_scope,
            "manual_request_requires_core_change": requires_core_change,
            "evidence_paths": evidence,
        }
        if created_at:
            source["created_at"] = created_at
        override = overrides.get(request_id) if isinstance(overrides, dict) else None
        if isinstance(override, dict):
            source["override_bucket"] = override.get("override_bucket")
            source["override_severity"] = override.get("override_severity")
            source["override_priority"] = override.get("override_priority")
            extra_evidence = override.get("override_evidence") if isinstance(override.get("override_evidence"), list) else []
            if extra_evidence:
                source["evidence_paths"] = list(source.get("evidence_paths") or []) + list(extra_evidence)

        sources.append(source)
    return sources


def run_work_intake_build(*, workspace_root: Path) -> dict[str, Any]:
    core_root = _find_repo_root(Path(__file__).resolve())
    policy, policy_notes = _load_policy(core_root=core_root, workspace_root=workspace_root)
    notes: list[str] = list(policy_notes)
    autopilot_policy, _, autopilot_notes = _load_autopilot_policy(
        core_root=core_root, workspace_root=workspace_root
    )
    notes.extend(autopilot_notes)
    selected_ids = _load_autopilot_selection(workspace_root, notes)
    if not policy or policy.get("version") != "v2":
        policy = _policy_defaults()
        notes.append("policy_fallback_defaults")

    if not bool(policy.get("enabled", True)):
        return {"status": "IDLE", "reason": "policy_disabled"}

    generated_at = _now_iso()

    sources: list[dict[str, Any]] = []
    sources.extend(_load_gap_sources(workspace_root, notes))
    sources.extend(_load_regression_sources(workspace_root, notes))
    sources.extend(_load_script_budget_sources(core_root, workspace_root, notes))
    sources.extend(_load_doc_nav_sources(workspace_root, notes))
    sources.extend(_load_integrity_sources(workspace_root, notes))
    sources.extend(_load_release_sources(workspace_root, notes))
    sources.extend(_load_github_ops_sources(workspace_root, notes))
    sources.extend(_load_deploy_job_sources(workspace_root, notes))
    sources.extend(_load_job_status_sources(workspace_root, notes))
    sources.extend(_load_time_sink_sources(workspace_root, notes))
    overrides = _load_context_router_overrides(workspace_root, notes)
    sources.extend(_load_manual_request_sources(workspace_root, notes, overrides))
    sources = _apply_job_status_cooldown(sources, workspace_root, notes)
    sources = _apply_github_ops_cooldown(sources, workspace_root, notes)
    sources = _apply_deploy_job_cooldown(sources, workspace_root, notes)

    owner_tenant = "CORE"
    plan_policy = str(policy.get("plan_policy") or "optional")

    items: list[dict[str, Any]] = []
    for source in sources:
        source_type = str(source.get("source_type") or "")
        source_ref = str(source.get("source_ref") or "")
        if not source_type or not source_ref:
            continue
        rule: dict[str, Any] = {}
        override_bucket = source.get("override_bucket")
        if isinstance(override_bucket, str) and override_bucket:
            bucket = str(override_bucket)
            default_severity = {"INCIDENT": "S1", "PROJECT": "S2", "ROADMAP": "S2", "TICKET": "S3"}.get(bucket, "S3")
            default_priority = {"INCIDENT": "P1", "PROJECT": "P2", "ROADMAP": "P2", "TICKET": "P3"}.get(bucket, "P3")
            severity = str(source.get("override_severity") or default_severity)
            priority = str(source.get("override_priority") or default_priority)
            tags = source.get("override_tags") if isinstance(source.get("override_tags"), list) else []
        else:
            rule = _classify_source(source, policy)
            bucket = str(rule.get("bucket") or "TICKET")
            severity = str(rule.get("severity") or "S3")
            priority = str(rule.get("priority") or "P3")
            tags = rule.get("tags") if isinstance(rule.get("tags"), list) else []
        intake_id = _intake_id(source_type, source_ref, bucket)
        evidence_paths = _normalize_evidence(source.get("evidence_paths", []), workspace_root)
        title = str(source.get("title") or f"{source_type}: {source_ref}")
        sla_hints = policy.get("sla_hints") if isinstance(policy.get("sla_hints"), dict) else {}
        sla_hint = str(sla_hints.get(bucket, "")) if isinstance(sla_hints, dict) else ""

        status = "OPEN"
        closed_reason = None
        if bool(rule.get("auto_close", False)):
            status = "DONE"
            closed_reason = str(rule.get("closed_reason") or "AUTO_CLOSE")

        item = {
            "intake_id": intake_id,
            "bucket": bucket,
            "severity": severity,
            "priority": priority,
            "status": status,
            "title": title,
            "source_type": source_type,
            "source_ref": source_ref,
            "evidence_paths": evidence_paths,
            "owner_tenant": owner_tenant,
            "layer": "L2",
        }
        last_seen = str(source.get("last_seen") or source.get("job_last_seen") or "")
        if last_seen:
            item["last_seen"] = last_seen
        last_status = str(source.get("last_status") or source.get("job_last_status") or "")
        if last_status:
            item["last_status"] = last_status
        updated_at = str(
            source.get("updated_at")
            or source.get("last_seen")
            or source.get("job_last_seen")
            or source.get("created_at")
            or ""
        )
        if updated_at:
            item["updated_at"] = updated_at
        item["ingested_at"] = generated_at
        if closed_reason:
            item["closed_reason"] = closed_reason
        suggested = _suggested_extensions(source, bucket)
        if suggested:
            item["suggested_extension"] = sorted({str(x) for x in suggested if isinstance(x, str) and x})
        if tags:
            item["tags"] = [str(t) for t in tags if isinstance(t, str)]
        if sla_hint:
            item["sla_hint"] = sla_hint
        lens_id = source.get("lens_id")
        if isinstance(lens_id, str) and lens_id:
            item["lens_id"] = lens_id
        lens_reason = source.get("lens_reason")
        if isinstance(lens_reason, str) and lens_reason:
            item["lens_reason"] = lens_reason
        autopilot_allowed, autopilot_selected, autopilot_reason, autopilot_notes = _autopilot_labels(
            item, source, autopilot_policy, selected_ids
        )
        item["autopilot_allowed"] = autopilot_allowed
        item["autopilot_selected"] = autopilot_selected
        if autopilot_reason:
            item["autopilot_reason"] = autopilot_reason
        if autopilot_notes:
            item["autopilot_notes"] = autopilot_notes
        items.append(item)

    applied_ids = _load_exec_ticket_applied_ids(workspace_root, notes)
    if applied_ids:
        for item in items:
            if item.get("intake_id") in applied_ids and item.get("status") != "DONE":
                item["status"] = "DONE"
                item["closed_reason"] = "EXEC_APPLIED"

    # Persistent close/applied/noop state (explicit close) should override transient intake status.
    # This is fail-closed: only FINAL_STATES affect visibility.
    state_map = load_state_map(workspace_root)
    if state_map:
        for item in items:
            intake_id = str(item.get("intake_id") or "")
            if not intake_id:
                continue
            state_entry = state_map.get(intake_id)
            if not isinstance(state_entry, dict):
                continue
            state = str(state_entry.get("state") or "")
            if state not in FINAL_STATES:
                continue
            if item.get("status") != "DONE":
                item["status"] = "DONE"
            if not item.get("closed_reason"):
                item["closed_reason"] = f"WORK_ITEM_STATE_{state}"

    bucket_order = policy.get("bucket_order") if isinstance(policy.get("bucket_order"), list) else []
    if not bucket_order:
        bucket_order = ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"]
    bucket_rank = {str(b): i for i, b in enumerate(bucket_order)}
    items.sort(
        key=lambda x: (
            bucket_rank.get(str(x.get("bucket")), 99),
            _priority_rank(str(x.get("priority"))),
            str(x.get("intake_id")),
        )
    )

    counts_by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    for item in items:
        bucket = item.get("bucket")
        if bucket in counts_by_bucket:
            counts_by_bucket[bucket] += 1

    top_next_actions = []
    for item in items[:5]:
        summary_item = {
            "intake_id": item.get("intake_id"),
            "bucket": item.get("bucket"),
            "severity": item.get("severity"),
            "priority": item.get("priority"),
            "status": item.get("status"),
            "title": item.get("title"),
            "source_type": item.get("source_type"),
            "source_ref": item.get("source_ref"),
        }
        suggested = item.get("suggested_extension")
        if isinstance(suggested, list) and suggested:
            summary_item["suggested_extension"] = suggested
        if "autopilot_allowed" in item:
            summary_item["autopilot_allowed"] = item.get("autopilot_allowed")
        if "autopilot_selected" in item:
            summary_item["autopilot_selected"] = item.get("autopilot_selected")
        if "autopilot_reason" in item:
            summary_item["autopilot_reason"] = item.get("autopilot_reason")
        if "autopilot_notes" in item:
            summary_item["autopilot_notes"] = item.get("autopilot_notes")
        if "lens_id" in item:
            summary_item["lens_id"] = item.get("lens_id")
        if "lens_reason" in item:
            summary_item["lens_reason"] = item.get("lens_reason")
        top_next_actions.append(summary_item)

    next_focus = "NONE"
    if top_next_actions:
        first = top_next_actions[0]
        if isinstance(first, dict):
            bucket = first.get("bucket") or ""
            intake_id = first.get("intake_id") or ""
            if bucket and intake_id:
                next_focus = f"{bucket}:{intake_id}"

    status = "OK" if items else "IDLE"
    warn_notes = [
        n
        for n in notes
        if not str(n).startswith(("job_status_suppressed=", "github_ops_suppressed=", "deploy_job_suppressed="))
    ]
    if warn_notes and status == "OK":
        status = "WARN"

    payload = {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "status": status,
        "plan_policy": plan_policy if plan_policy in {"optional", "required"} else "optional",
        "items": items,
        "summary": {
            "total_count": len(items),
            "counts_by_bucket": counts_by_bucket,
            "top_next_actions": top_next_actions,
            "next_intake_focus": next_focus,
        },
        "notes": sorted(set(notes)),
    }

    out_json = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "work_intake_summary.v1.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Work Intake Summary (v0.2)",
        "",
        f"Total items: {len(items)}",
        f"Next focus: {next_focus}",
        "",
        "Counts by bucket:",
        f"- INCIDENT: {counts_by_bucket.get('INCIDENT', 0)}",
        f"- TICKET: {counts_by_bucket.get('TICKET', 0)}",
        f"- PROJECT: {counts_by_bucket.get('PROJECT', 0)}",
        f"- ROADMAP: {counts_by_bucket.get('ROADMAP', 0)}",
        "",
        "Top next actions:",
    ]
    for item in top_next_actions:
        lines.append(
            f"- {item.get('intake_id', '')} bucket={item.get('bucket', '')} "
            f"severity={item.get('severity', '')} priority={item.get('priority', '')}"
        )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rel_json = _rel_to_workspace(out_json, workspace_root) or str(out_json)
    rel_md = _rel_to_workspace(out_md, workspace_root) or str(out_md)

    return {
        "status": status,
        "work_intake_path": rel_json,
        "summary_path": rel_md,
        "items_count": len(items),
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions,
        "next_intake_focus": next_focus,
    }
