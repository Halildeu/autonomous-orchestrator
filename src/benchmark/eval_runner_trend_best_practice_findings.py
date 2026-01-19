from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import (
    _extract_domains_from_tags,
    _extract_topic_from_tags,
    _finalize_findings_v1,
    _infer_topic_from_tags,
    _normalize_tag_list,
    _rel_evidence_pointer,
)


def _build_trend_best_practice_findings_impl(
    *,
    workspace_root: Path,
    raw_ref: str,
    thresholds: dict[str, Any],
    facts: dict[str, Any],
    trend_items: list[dict[str, Any]],
    bp_items: list[dict[str, Any]],
    evidence_paths: dict[str, Any],
) -> dict[str, Any]:
    raw_ref_norm = (
        raw_ref
        if isinstance(raw_ref, str) and raw_ref.strip()
        else str(Path(".cache") / "index" / "assessment_raw.v1.json")
    )

    def _resolve_threshold(key: str, default: float) -> float:
        val = thresholds.get(key, default)
        if isinstance(val, (int, float)):
            return float(val)
        return float(default)

    placeholders_warn = _resolve_threshold("placeholders_warn", 25)
    soft_warn = _resolve_threshold("soft_warn", 1)
    pdca_warn = _resolve_threshold("pdca_cursor_stale_hours_warn", 24)
    heartbeat_warn = _resolve_threshold("heartbeat_stale_seconds_warn", 1800)
    jobs_stuck_warn = _resolve_threshold("jobs_stuck_warn", 1)
    jobs_fail_warn = _resolve_threshold("jobs_fail_warn", 3)
    intake_new_warn = _resolve_threshold("intake_new_items_per_day_warn", 25)
    suppressed_warn = _resolve_threshold("suppressed_per_day_warn", 200)

    def _topic_match(topic: str) -> tuple[str, list[str], list[str]]:
        # Returns: (match_status, reasons, evidence_pointers)
        reasons: list[str] = []
        evid: set[str] = {raw_ref_norm}

        def _add(reason: str, *evidence_keys: str) -> None:
            reasons.append(reason)
            for k in evidence_keys:
                p = _rel_evidence_pointer(workspace_root, evidence_paths.get(k))
                if p:
                    evid.add(p)

        if not topic:
            return ("UNKNOWN", [], sorted(evid))

        hard_exceeded = int(facts.get("hard_exceeded", 0) or 0)
        soft_exceeded = int(facts.get("soft_exceeded", 0) or 0)
        placeholders = int(facts.get("placeholders", 0) or 0)
        broken_refs = int(facts.get("broken_refs", 0) or 0)
        orphan_critical = int(facts.get("orphan_critical", 0) or 0)
        docs_unmapped = int(facts.get("docs_unmapped_md_count", 0) or 0)
        pdca_stale = float(facts.get("pdca_stale_hours", 0.0) or 0.0)
        heartbeat_stale = int(facts.get("heartbeat_stale_seconds", 0) or 0)
        jobs_stuck = int(facts.get("jobs_stuck", 0) or 0)
        jobs_fail = int(facts.get("jobs_fail", 0) or 0)
        intake_new = int(facts.get("intake_new_items_24h", 0) or 0)
        suppressed = int(facts.get("suppressed_24h", 0) or 0)
        integrity_status = str(facts.get("integrity_status", "") or "")
        layer_boundary_violations = int(facts.get("layer_boundary_violations", 0) or 0)
        pack_conflicts = int(facts.get("pack_conflicts", 0) or 0)
        core_unlock_scope_widen = int(facts.get("core_unlock_scope_widen", 0) or 0)
        schema_fail_count = int(facts.get("schema_fail_count", 0) or 0)
        auto_mode_enabled = bool(facts.get("auto_mode_enabled", False))
        secrets_redacted = bool(facts.get("secrets_redacted", False))
        provider_policy_pinned = bool(facts.get("provider_policy_pinned", False))
        github_ops_network_default_off = bool(facts.get("github_ops_network_default_off", False))

        if topic == "ai_otomasyon":
            if not auto_mode_enabled:
                _add("auto_mode_disabled", "airrunner_jobs_index_path")
        elif topic == "baglam_uyum":
            if docs_unmapped > 0:
                _add("docs_drift_unmapped_md_gt0")
            if core_unlock_scope_widen > 0:
                _add("core_unlock_scope_widen_gt0", "core_unlock_compliance_path")
            if layer_boundary_violations > 0:
                _add("layer_boundary_violations_gt0")
        elif topic == "kalite_dogruluk":
            if integrity_status and integrity_status != "PASS":
                _add("integrity_not_pass", "integrity_snapshot_ref")
            if schema_fail_count > 0:
                _add("schema_fail_gt0")
        elif topic == "zaman_hiz_ceviklik":
            if jobs_stuck >= jobs_stuck_warn:
                _add("jobs_stuck_ge_warn", "airrunner_jobs_index_path")
            if jobs_fail >= jobs_fail_warn:
                _add("jobs_fail_ge_warn", "airrunner_jobs_index_path")
        elif topic == "maliyet_verimlilik_kaynak":
            if hard_exceeded > 0:
                _add("script_budget_hard_exceeded_gt0", "script_budget_report_path")
            if soft_exceeded >= soft_warn:
                _add("script_budget_soft_exceeded_ge_warn", "script_budget_report_path")
        elif topic == "guvenlik":
            if not provider_policy_pinned:
                _add("provider_policy_guardrails_missing", "assessment_eval_path")
            if not github_ops_network_default_off:
                _add("github_ops_network_default_off_missing_or_disabled", "assessment_eval_path")
        elif topic == "gizlilik":
            if not secrets_redacted:
                _add("secrets_redaction_policy_missing", "assessment_eval_path")
        elif topic == "uygunluk_risk_guvence_kontrol":
            if core_unlock_scope_widen > 0:
                _add("core_unlock_scope_widen_gt0", "core_unlock_compliance_path")
            if schema_fail_count > 0:
                _add("schema_fail_gt0")
            if suppressed >= suppressed_warn:
                _add("suppressed_24h_ge_warn")
        elif topic == "surec_etkinligi_olgunluk":
            if pdca_stale >= pdca_warn:
                _add("pdca_cursor_stale_hours_ge_warn")
            if intake_new >= intake_new_warn:
                _add("intake_new_items_24h_ge_warn")
            if suppressed >= suppressed_warn:
                _add("suppressed_24h_ge_warn")
        elif topic == "entegrasyon_birlikte_calisabilirlik":
            if pack_conflicts > 0:
                _add("pack_conflicts_gt0")
            if layer_boundary_violations > 0:
                _add("layer_boundary_violations_gt0")
        elif topic == "sureklilik_dayaniklilik":
            heartbeat_expected = bool(facts.get("heartbeat_expected_now", True))
            if heartbeat_stale >= heartbeat_warn:
                if heartbeat_expected:
                    _add("heartbeat_stale_seconds_ge_warn", "heartbeat_path")
            if jobs_stuck >= jobs_stuck_warn:
                _add("jobs_stuck_ge_warn", "airrunner_jobs_index_path")
        elif topic == "olceklenebilirlik":
            if intake_new >= intake_new_warn:
                _add("intake_new_items_24h_ge_warn")
        elif topic == "deterministiklik_tekrarlanabilirlik":
            if hard_exceeded > 0:
                _add("script_budget_hard_exceeded_gt0", "script_budget_report_path")
            if soft_exceeded >= soft_warn:
                _add("script_budget_soft_exceeded_ge_warn", "script_budget_report_path")
        elif topic == "gozlemlenebilirlik_izleme_olcme":
            if placeholders >= placeholders_warn:
                _add("doc_nav_placeholders_ge_warn", "doc_nav_report_path")
            if broken_refs > 0:
                _add("doc_nav_broken_refs_gt0", "doc_nav_report_path")
            if orphan_critical > 0:
                _add("doc_nav_orphan_critical_gt0", "doc_nav_report_path")
        else:
            return ("UNKNOWN", [], sorted(evid))

        status = "TRIGGERED" if reasons else "NOT_TRIGGERED"
        reasons = sorted(set(reasons))
        return (status, reasons, sorted(evid))

    def _build_item(*, catalog: str, item: dict[str, Any]) -> dict[str, Any]:
        tags = _normalize_tag_list(item.get("tags"))
        topic = _extract_topic_from_tags(tags) or _infer_topic_from_tags(tags)
        domains = _extract_domains_from_tags(tags)
        match_status, reasons, evidence = _topic_match(topic)
        theme_id = str(item.get("theme_id") or "").strip()
        theme_title_tr = str(item.get("theme_title_tr") or "").strip()
        subtheme_id = str(item.get("subtheme_id") or "").strip()
        subtheme_title_tr = str(item.get("subtheme_title_tr") or "").strip()
        payload: dict[str, Any] = {
            "catalog": catalog,
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "tags": tags,
            "domains": domains,
            "topic": topic,
            "match_status": match_status,
            "reasons": reasons,
            "evidence_pointers": evidence,
        }
        if theme_id:
            payload["theme_id"] = theme_id
        if theme_title_tr:
            payload["theme_title_tr"] = theme_title_tr
        if subtheme_id:
            payload["subtheme_id"] = subtheme_id
        if subtheme_title_tr:
            payload["subtheme_title_tr"] = subtheme_title_tr

        summary = str(item.get("summary") or "").strip()
        if summary:
            payload["summary"] = summary

        evidence_expectations = item.get("evidence_expectations")
        if isinstance(evidence_expectations, list):
            normalized_expectations = [
                str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()
            ]
            if normalized_expectations:
                payload["evidence_expectations"] = normalized_expectations

        remediation = item.get("remediation")
        if isinstance(remediation, list):
            normalized_remediation = [str(x).strip() for x in remediation if isinstance(x, str) and str(x).strip()]
            if normalized_remediation:
                payload["remediation"] = normalized_remediation

        return payload

    findings_items: list[dict[str, Any]] = []
    for item in trend_items:
        findings_items.append(_build_item(catalog="trend", item=item))
    for item in bp_items:
        findings_items.append(_build_item(catalog="bp", item=item))

    return _finalize_findings_v1(findings_items)
