from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import (
    _extract_domains_from_tags,
    _finalize_findings_v1,
    _normalize_tag_list,
    _rel_evidence_pointer,
)
from src.benchmark.operability_check_details_v1 import OPERABILITY_CHECK_DETAILS_V1, OPERABILITY_REASON_MAP_V1


def _build_operability_findings_impl(
    *,
    workspace_root: Path,
    raw_ref: str,
    required_map: dict[str, bool],
    thresholds: dict[str, Any],
    warn_cfg: dict[str, Any],
    fail_cfg: dict[str, Any],
    values: dict[str, Any],
    fail_reasons: list[str],
    warn_reasons: list[str],
    evidence_paths: dict[str, Any],
) -> dict[str, Any]:
    raw_ref_norm = (
        raw_ref
        if isinstance(raw_ref, str) and raw_ref.strip()
        else str(Path(".cache") / "index" / "assessment_raw.v1.json")
    )

    def _resolve_threshold(value: Any) -> float:
        if isinstance(value, str):
            return float(thresholds.get(value, 0) or 0)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    # First: required signal presence items (actionable when missing).
    required_items: list[dict[str, Any]] = []
    required_topics = {
        "script_budget_present": "maliyet_verimlilik_kaynak",
        "doc_nav_present": "gozlemlenebilirlik_izleme_olcme",
        "docs_hygiene_present": "surec_etkinligi_olgunluk",
        "docs_drift_present": "baglam_uyum",
        "airunner_jobs_present": "sureklilik_dayaniklilik",
        "pdca_cursor_present": "surec_etkinligi_olgunluk",
        "heartbeat_present": "sureklilik_dayaniklilik",
        "work_intake_present": "surec_etkinligi_olgunluk",
        "integrity_present": "kalite_dogruluk",
    }
    required_details: dict[str, dict[str, Any]] = {
        "script_budget_present": {
            "summary": "Script budget; ağır işlemlerin kaynak sınırını ölçer. Yoksa maliyet/verimlilik takibi yapılamaz.",
            "evidence_expectations": ["`.cache/script_budget/report.json` mevcut ve json_valid."],
            "remediation": ["script-budget op’unu çalıştır ve raporu closeout’a ekle."],
        },
        "doc_nav_present": {
            "summary": "Doc-nav; doküman link bütünlüğü ve placeholder’ları ölçer. Yoksa gözlemlenebilirlik zayıflar.",
            "evidence_expectations": ["`.cache/reports/doc_graph_report.strict.v1.json` mevcut ve strict sonuç içerir."],
            "remediation": ["doc-nav-check’i (strict) çalıştır; gerekiyorsa jobify/tick yaklaşımı kullan."],
        },
        "docs_hygiene_present": {
            "summary": "Docs hygiene; markdown sayımı/byte gibi repo hijyen metriklerini üretir.",
            "evidence_expectations": ["`.cache/reports/repo_hygiene.v1.json` mevcut ve json_valid."],
            "remediation": ["repo-hygiene op’unu çalıştır ve ops docs kapsamını doğru ayarla."],
        },
        "docs_drift_present": {
            "summary": "Docs drift; dokümanların nav/SSOT ile uyumunu ölçer (unmapped/orphan risk).",
            "evidence_expectations": ["`.cache/reports/docs_drift_signal.v1.json` mevcut ve json_valid."],
            "remediation": ["docs drift sinyalini üret; mapping/allowlist’i güncelle."],
        },
        "airunner_jobs_present": {
            "summary": "Airunner jobs; stuck/fail oranlarını ölçer. Yoksa süreklilik/dayanıklılık izlenemez.",
            "evidence_expectations": ["`.cache/airrunner/jobs_index.v1.json` mevcut ve json_valid."],
            "remediation": ["airrunner jobs index üretimini doğrula; gerekirse jobs poll/tick çalıştır."],
        },
        "pdca_cursor_present": {
            "summary": "PDCA cursor; sürekli iyileştirme döngüsü için tazelik/ilerleme sinyali sağlar.",
            "evidence_expectations": ["`.cache/index/pdca_cursor.v1.json` mevcut ve json_valid."],
            "remediation": ["pdca-recheck’i cooldown+budget gate ile planla/çalıştır."],
        },
        "heartbeat_present": {
            "summary": "Heartbeat; sistemin yakın zamanda aktif olup olmadığını ölçer. Expectation mode’a göre stale anlamlıdır.",
            "evidence_expectations": ["`.cache/airrunner/airrunner_heartbeat.v1.json` mevcut ve json_valid."],
            "remediation": ["Heartbeat üretimini kanıtla; gerekirse budget+cooldown ile refresh uygula."],
        },
        "work_intake_present": {
            "summary": "Work intake; backlog ve suppress/new_items gibi gürültü metriklerini üretir.",
            "evidence_expectations": ["`.cache/index/work_intake.v1.json` mevcut ve json_valid."],
            "remediation": ["work-intake-check çalıştır; timestamp/dedup alanlarını doğrula."],
        },
        "integrity_present": {
            "summary": "Integrity; temel okuma/şema bütünlüğünün PASS olması gerekir. Yoksa lens çıktıları güvenilmezdir.",
            "evidence_expectations": ["Integrity snapshot verify_on_read_result=PASS."],
            "remediation": ["integrity verify çalıştır; FAIL ise report-only modda dur."],
        },
    }
    for key in sorted(required_map.keys()):
        ok = bool(required_map.get(key, False))
        topic = required_topics.get(key, "")
        all_tags = _normalize_tag_list(
            ["core", "domain_operability", "lens:operability", f"signal:{key}", f"topic:{topic}"]
        )
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"operability.signal.{key}",
            "title": f"Required signal present: {key}",
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": "NOT_TRIGGERED" if ok else "TRIGGERED",
            "reasons": [] if ok else ["missing_required_signal"],
            "evidence_pointers": sorted(set([raw_ref_norm, str(Path(".cache") / "index" / "assessment_raw.v1.json")])),
        }
        details = required_details.get(key, {})
        summary = details.get("summary")
        if isinstance(summary, str) and summary.strip():
            payload["summary"] = summary.strip()
        evidence_expectations = details.get("evidence_expectations")
        if isinstance(evidence_expectations, list):
            ee = [str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()]
            if ee:
                payload["evidence_expectations"] = ee
        remediation = details.get("remediation")
        if isinstance(remediation, list):
            rem = [str(x).strip() for x in remediation if isinstance(x, str) and str(x).strip()]
            if rem:
                payload["remediation"] = rem
        required_items.append(payload)

    # Second: threshold checks (only meaningful when backing signal present).
    check_specs: list[tuple[str, str, str, str, list[str], str]] = [
        (
            "hard_exceeded_gt",
            "script_budget_present",
            "maliyet_verimlilik_kaynak",
            "Script budget hard exceeded",
            ["script_budget"],
            "script_budget_report_path",
        ),
        (
            "soft_exceeded_gt",
            "script_budget_present",
            "maliyet_verimlilik_kaynak",
            "Script budget soft exceeded",
            ["script_budget"],
            "script_budget_report_path",
        ),
        (
            "integrity_fail",
            "integrity_present",
            "kalite_dogruluk",
            "Integrity status FAIL",
            ["integrity"],
            "integrity_snapshot_ref",
        ),
        (
            "jobs_stuck_gt",
            "airunner_jobs_present",
            "sureklilik_dayaniklilik",
            "Jobs stuck",
            ["jobs"],
            "airrunner_jobs_index_path",
        ),
        (
            "jobs_fail_gt",
            "airunner_jobs_present",
            "zaman_hiz_ceviklik",
            "Jobs failed",
            ["jobs"],
            "airrunner_jobs_index_path",
        ),
        (
            "pdca_cursor_stale_hours_gt",
            "pdca_cursor_present",
            "surec_etkinligi_olgunluk",
            "PDCA cursor stale hours",
            ["pdca"],
            str(Path(".cache") / "index" / "pdca_cursor.v1.json"),
        ),
        (
            "heartbeat_stale_seconds_gt",
            "heartbeat_present",
            "sureklilik_dayaniklilik",
            "Heartbeat stale seconds",
            ["heartbeat"],
            "heartbeat_path",
        ),
        (
            "placeholders_gt",
            "doc_nav_present",
            "gozlemlenebilirlik_izleme_olcme",
            "Doc-nav placeholders",
            ["doc_nav"],
            "doc_nav_report_path",
        ),
        (
            "docs_ops_md_count_gt",
            "docs_hygiene_present",
            "surec_etkinligi_olgunluk",
            "Docs ops markdown count",
            ["docs_hygiene"],
            str(Path(".cache") / "reports" / "repo_hygiene.v1.json"),
        ),
        (
            "docs_ops_md_bytes_gt",
            "docs_hygiene_present",
            "surec_etkinligi_olgunluk",
            "Docs ops markdown bytes",
            ["docs_hygiene"],
            str(Path(".cache") / "reports" / "repo_hygiene.v1.json"),
        ),
        (
            "repo_md_total_count_gt",
            "docs_hygiene_present",
            "surec_etkinligi_olgunluk",
            "Repo markdown total count",
            ["docs_hygiene"],
            str(Path(".cache") / "reports" / "repo_hygiene.v1.json"),
        ),
        (
            "docs_unmapped_md_gt",
            "docs_drift_present",
            "baglam_uyum",
            "Docs drift unmapped markdown",
            ["docs_drift"],
            str(Path(".cache") / "reports" / "docs_drift_signal.v1.json"),
        ),
        (
            "intake_new_items_per_day_gt",
            "work_intake_present",
            "surec_etkinligi_olgunluk",
            "Work intake new items (24h)",
            ["work_intake"],
            str(Path(".cache") / "index" / "work_intake.v1.json"),
        ),
        (
            "suppressed_per_day_gt",
            "work_intake_present",
            "surec_etkinligi_olgunluk",
            "Work intake suppressed (24h)",
            ["work_intake"],
            str(Path(".cache") / "index" / "work_intake.v1.json"),
        ),
    ]

    def _reason_code(key: str) -> str:
        return OPERABILITY_REASON_MAP_V1.get(key, key)

    check_items: list[dict[str, Any]] = []
    check_details: dict[str, dict[str, Any]] = OPERABILITY_CHECK_DETAILS_V1
    for check_key, req_key, topic, title, extra_tags, evidence_key in check_specs:
        has_signal = bool(required_map.get(req_key, False))
        all_tags = _normalize_tag_list(
            ["core", "domain_operability", "lens:operability", f"check:{check_key}", f"topic:{topic}", *extra_tags]
        )
        evid: set[str] = {raw_ref_norm}

        # Evidence pointer: prefer explicit key mapping from evidence_paths dict.
        if isinstance(evidence_key, str) and evidence_key in evidence_paths:
            p = _rel_evidence_pointer(workspace_root, evidence_paths.get(evidence_key))
            if p:
                evid.add(p)
        else:
            # Evidence pointer: treat as already relative workspace path.
            if isinstance(evidence_key, str) and evidence_key.strip():
                evid.add(Path(evidence_key).as_posix())

        if not has_signal:
            match_status = "UNKNOWN"
            reasons = ["missing_required_signal"]
        else:
            # Determine triggered vs not_triggered using the same FAIL/WARN rules as operability classification.
            code = _reason_code(check_key)
            level = None
            if code in fail_reasons:
                level = "FAIL"
            elif code in warn_reasons:
                level = "WARN"

            if level is None:
                match_status = "NOT_TRIGGERED"
                reasons = []
            else:
                match_status = "TRIGGERED"
                reasons = [f"{code}:{level}"]

        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"operability.{check_key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set(reasons)),
            "evidence_pointers": sorted(evid),
        }
        details = check_details.get(check_key, {})
        if details:
            last = payload
            summary = details.get("summary")
            if isinstance(summary, str) and summary.strip():
                last["summary"] = summary.strip()
            ee = details.get("evidence_expectations")
            if isinstance(ee, list):
                ee_norm = [str(x).strip() for x in ee if isinstance(x, str) and str(x).strip()]
                if ee_norm:
                    last["evidence_expectations"] = ee_norm
            rem = details.get("remediation")
            if isinstance(rem, list):
                rem_norm = [str(x).strip() for x in rem if isinstance(x, str) and str(x).strip()]
                if rem_norm:
                    last["remediation"] = rem_norm
        check_items.append(payload)

    return _finalize_findings_v1([*required_items, *check_items])

