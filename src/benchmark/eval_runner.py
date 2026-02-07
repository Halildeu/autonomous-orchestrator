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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key) or {}, value)
        else:
            merged[key] = value
    return merged


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _write_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _normalize_tag_list(value: Any) -> list[str]:
    tags_raw = value if isinstance(value, list) else []
    tags = [str(t).strip() for t in tags_raw if isinstance(t, str) and t.strip()]
    return sorted(set(tags))


def _extract_topic_from_tags(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("topic:"):
            return tag.split(":", 1)[1].strip()
    return ""


def _extract_domains_from_tags(tags: list[str]) -> list[str]:
    domains = [t for t in tags if t.startswith("domain_")]
    if "core" in tags:
        domains.append("core")
    return sorted(set(domains))


def _infer_topic_from_tags(tags: list[str]) -> str:
    # Best-effort mapping for non-core items that don't carry explicit topic:* tag.
    # This is intentionally conservative and should be extended as more signals become available.
    tag_set = set(tags)
    if "doc_nav" in tag_set or "jobify" in tag_set:
        return "gozlemlenebilirlik_izleme_olcme"
    if {"alignment", "context", "drift", "boundary", "scope"} & tag_set:
        return "baglam_uyum"
    if "integration" in tag_set:
        return "entegrasyon_birlikte_calisabilirlik"
    if {"determinism", "io", "safety"} & tag_set:
        return "deterministiklik_tekrarlanabilirlik"
    if {"policy", "security", "compliance", "gates"} & tag_set:
        return "uygunluk_risk_guvence_kontrol"
    if {"triage", "ops", "pipeline"} & tag_set:
        return "surec_etkinligi_olgunluk"
    if {"intake", "stale", "pdca", "gaps"} & tag_set:
        return "surec_etkinligi_olgunluk"
    if "offline" in tag_set or "seed" in tag_set:
        return "surec_etkinligi_olgunluk"
    return ""


def _rel_evidence_pointer(workspace_root: Path, path_value: Any) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        return ""
    candidate = Path(path_value)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        rel = candidate.resolve().relative_to(workspace_root.resolve())
    except Exception:
        return ""
    return rel.as_posix()


def _safe_load_catalog_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []

    def _normalize_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if s:
                out.append(s)
        return out

    items = obj.get("items") if isinstance(obj, dict) else None
    items_list = items if isinstance(items, list) else []
    normalized: list[dict[str, Any]] = []
    for item in items_list:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not item_id or not title:
            continue
        tags = _normalize_tag_list(item.get("tags"))
        summary = str(item.get("summary") or "").strip()
        evidence_expectations = _normalize_str_list(item.get("evidence_expectations"))
        remediation = _normalize_str_list(item.get("remediation"))

        payload: dict[str, Any] = {
            "id": item_id,
            "title": title,
            "tags": tags,
        }
        if summary:
            payload["summary"] = summary
        if evidence_expectations:
            payload["evidence_expectations"] = evidence_expectations
        if remediation:
            payload["remediation"] = remediation

        normalized.append(payload)
    normalized.sort(key=lambda entry: entry["id"])
    return normalized


def _finalize_findings_v1(items: list[dict[str, Any]]) -> dict[str, Any]:
    # Deterministic output ordering.
    items_sorted = sorted(items, key=lambda f: (str(f.get("catalog") or ""), str(f.get("id") or "")))
    total = len(items_sorted)
    triggered = len([x for x in items_sorted if x.get("match_status") == "TRIGGERED"])
    unknown = len([x for x in items_sorted if x.get("match_status") == "UNKNOWN"])
    not_triggered = total - triggered - unknown
    return {
        "version": "v1",
        "summary": {
            "total": int(total),
            "triggered": int(triggered),
            "not_triggered": int(not_triggered),
            "unknown": int(unknown),
        },
        "items": items_sorted,
    }


def _build_trend_best_practice_findings(
    *,
    workspace_root: Path,
    raw_ref: str,
    thresholds: dict[str, Any],
    facts: dict[str, Any],
    trend_items: list[dict[str, Any]],
    bp_items: list[dict[str, Any]],
    evidence_paths: dict[str, Any],
) -> dict[str, Any]:
    raw_ref_norm = raw_ref if isinstance(raw_ref, str) and raw_ref.strip() else str(Path(".cache") / "index" / "assessment_raw.v1.json")

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

        summary = str(item.get("summary") or "").strip()
        if summary:
            payload["summary"] = summary

        evidence_expectations = item.get("evidence_expectations")
        if isinstance(evidence_expectations, list):
            normalized_expectations = [str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()]
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


def _build_ai_ops_fit_findings(
    *,
    workspace_root: Path,
    raw_ref: str,
    requirements: dict[str, bool],
) -> dict[str, Any]:
    raw_ref_norm = raw_ref if isinstance(raw_ref, str) and raw_ref.strip() else str(Path(".cache") / "index" / "assessment_raw.v1.json")
    items: list[dict[str, Any]] = []

    def _add_item(
        *,
        key: str,
        title: str,
        topic: str,
        tags: list[str],
        reasons_triggered: list[str],
        evidence_pointers: list[str],
        summary: str,
        evidence_expectations: list[str],
        remediation: list[str],
    ) -> None:
        ok = bool(requirements.get(key, False))
        match_status = "NOT_TRIGGERED" if ok else "TRIGGERED"
        all_tags = _normalize_tag_list(["core", "domain_ai", f"lens:ai_ops_fit", f"requirement:{key}", f"topic:{topic}", *tags])
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"ai_ops_fit.{key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set([] if ok else reasons_triggered)),
            "evidence_pointers": sorted(set([raw_ref_norm, *[p for p in evidence_pointers if isinstance(p, str) and p.strip()]])),
        }
        if isinstance(summary, str) and summary.strip():
            payload["summary"] = summary.strip()
        if isinstance(evidence_expectations, list):
            ee = [str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()]
            if ee:
                payload["evidence_expectations"] = ee
        if isinstance(remediation, list):
            rem = [str(x).strip() for x in remediation if isinstance(x, str) and str(x).strip()]
            if rem:
                payload["remediation"] = rem
        items.append(payload)

    _add_item(
        key="context_pack_present",
        title="Context pack present",
        topic="baglam_uyum",
        tags=["context_pack"],
        reasons_triggered=["missing_context_pack"],
        evidence_pointers=[str(Path(".cache") / "index" / "context_pack.v1.json")],
        summary="Context pack; amaç/kapsam/kısıtlar/kabul kriterlerini tek yerde toplar. Eksikse AI çıktıları drift etme eğilimindedir.",
        evidence_expectations=[
            "`.cache/index/context_pack.v1.json` mevcut ve şema-valid.",
            "Plan/çıktı ile istek arasında izlenebilir bağ (evidence pointers) var.",
        ],
        remediation=[
            "Kısa bir context_pack oluştur (amaç, kapsam, kısıtlar, kabul kriterleri, sözlük).",
            "Context pack’i North Star/contract test zincirine dahil et.",
        ],
    )
    _add_item(
        key="provider_policy_pinned",
        title="LLM provider guardrails policy present",
        topic="uygunluk_risk_guvence_kontrol",
        tags=["policy", "providers"],
        reasons_triggered=["missing_provider_policy"],
        evidence_pointers=[str(Path("policies") / "policy_llm_providers_guardrails.v1.json")],
        summary="LLM provider guardrails; hangi provider/modelin hangi koşullarda kullanılacağını ve güvenlik/mahremiyet sınırlarını belirler.",
        evidence_expectations=[
            "`policies/policy_llm_providers_guardrails.v1.json` mevcut ve policy-check PASS.",
            "Varsayılan NO_NETWORK ve secrets redaction ile uyumlu.",
        ],
        remediation=[
            "Provider allowlist + guardrail policy ekle (network, data handling, model selection).",
            "Policy değişimini closeout + evidence ile kayıt altına al.",
        ],
    )
    _add_item(
        key="secrets_redacted",
        title="Secrets policy present (redaction enforced)",
        topic="uygunluk_risk_guvence_kontrol",
        tags=["policy", "secrets"],
        reasons_triggered=["missing_secrets_policy"],
        evidence_pointers=[str(Path("policies") / "policy_secrets.v1.json")],
        summary="Secrets redaction; token/anahtar gibi gizli verilerin log/evidence içine sızmasını engeller.",
        evidence_expectations=[
            "`policies/policy_secrets.v1.json` mevcut ve uygulanıyor.",
            "Loglarda `[REDACTED]` benzeri redaction işaretleri görülebiliyor.",
        ],
        remediation=[
            "Secrets policy’yi repo’ya ekle ve policy-check’e dahil et.",
            "Tüm raporlayıcılar için redaction zorunlu kıl (fail-closed).",
        ],
    )

    return _finalize_findings_v1(items)


def _build_github_ops_release_findings(
    *,
    workspace_root: Path,
    raw_ref: str,
    requirements: dict[str, bool],
) -> dict[str, Any]:
    raw_ref_norm = raw_ref if isinstance(raw_ref, str) and raw_ref.strip() else str(Path(".cache") / "index" / "assessment_raw.v1.json")

    def _item(
        *,
        key: str,
        title: str,
        topic: str,
        tags: list[str],
        reasons_triggered: list[str],
        evidence_pointers: list[str],
        summary: str,
        evidence_expectations: list[str],
        remediation: list[str],
    ) -> dict[str, Any]:
        ok = bool(requirements.get(key, False))
        match_status = "NOT_TRIGGERED" if ok else "TRIGGERED"
        all_tags = _normalize_tag_list(
            [
                "core",
                "domain_github_ops",
                "domain_release",
                "lens:github_ops_release",
                f"requirement:{key}",
                f"topic:{topic}",
                *tags,
            ]
        )
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"github_ops_release.{key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set([] if ok else reasons_triggered)),
            "evidence_pointers": sorted(set([raw_ref_norm, *[p for p in evidence_pointers if isinstance(p, str) and p.strip()]])),
        }
        if isinstance(summary, str) and summary.strip():
            payload["summary"] = summary.strip()
        if isinstance(evidence_expectations, list):
            ee = [str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()]
            if ee:
                payload["evidence_expectations"] = ee
        if isinstance(remediation, list):
            rem = [str(x).strip() for x in remediation if isinstance(x, str) and str(x).strip()]
            if rem:
                payload["remediation"] = rem
        return payload

    items = [
        _item(
            key="github_ops_policy_present",
            title="GitHub ops policy present",
            topic="uygunluk_risk_guvence_kontrol",
            tags=["policy", "github_ops"],
            reasons_triggered=["missing_policy_github_ops"],
            evidence_pointers=[str(Path("policies") / "policy_github_ops.v1.json")],
            summary="GitHub ops akışının guardrail’ları (network/secrets/determinism) policy ile tanımlı olmalı.",
            evidence_expectations=[
                "`policies/policy_github_ops.v1.json` mevcut ve policy-check PASS.",
                "NO_NETWORK default ve secrets redaction prensibi korunuyor.",
            ],
            remediation=[
                "policy_github_ops ekle/güncelle; network/secrets/determinism kurallarını netleştir.",
                "Policy değişiminde closeout + evidence üret.",
            ],
        ),
        _item(
            key="github_ops_network_default_off",
            title="GitHub ops policy: network default OFF",
            topic="uygunluk_risk_guvence_kontrol",
            tags=["policy", "network"],
            reasons_triggered=["network_default_on"],
            evidence_pointers=[str(Path("policies") / "policy_github_ops.v1.json")],
            summary="GitHub ops için varsayılan network kapalı olmalı; aksi drift ve güvenlik riskini artırır.",
            evidence_expectations=[
                "policy_github_ops içinde network default OFF (fail-closed).",
                "Network gerektiren adımlar explicit allowlist ile açılıyor.",
            ],
            remediation=[
                "Policy’de network default OFF yap; gerekli durumlarda tek-seferlik allowlist kullan.",
                "Network kullanımını closeout’ta kanıtla (network_used=false varsayılan).",
            ],
        ),
        _item(
            key="release_policy_present",
            title="Release automation policy present",
            topic="uygunluk_risk_guvence_kontrol",
            tags=["policy", "release"],
            reasons_triggered=["missing_policy_release_automation"],
            evidence_pointers=[str(Path("policies") / "policy_release_automation.v1.json")],
            summary="Release otomasyonu policy ile kısıtlanmalı; imzalama, içerik, kanıt ve güvenlik sınırları net olmalı.",
            evidence_expectations=[
                "`policies/policy_release_automation.v1.json` mevcut ve policy-check PASS.",
                "Release çıktıları şema-valid ve kanıtlı (manifest/plan).",
            ],
            remediation=[
                "policy_release_automation ekle ve varsayılanları fail-closed tut.",
                "Release artefact’ları için contract test ekle (manifest schema/semantic).",
            ],
        ),
        _item(
            key="github_jobs_index_present",
            title="GitHub ops jobs index present",
            topic="gozlemlenebilirlik_izleme_olcme",
            tags=["jobs_index", "github_ops"],
            reasons_triggered=["missing_jobs_index"],
            evidence_pointers=[str(Path(".cache") / "github_ops" / "jobs_index.v1.json")],
            summary="jobs_index; job’ları deterministik seçmek/triage etmek için gerekli temel indekstir.",
            evidence_expectations=[
                "`.cache/github_ops/jobs_index.v1.json` mevcut ve json_valid.",
                "Triage “latest” seçiminde jobs_index kullanıyor (started_at/job_id tie-break).",
            ],
            remediation=[
                "Job yazım sırasını garanti et (jobs_index → job report) ve yarış koşullarını azalt.",
                "Triage’ı explicit job_id ile çalıştırma standardı getir.",
            ],
        ),
        _item(
            key="release_manifest_present",
            title="Release manifest present",
            topic="surec_etkinligi_olgunluk",
            tags=["release_manifest"],
            reasons_triggered=["missing_release_manifest"],
            evidence_pointers=[str(Path(".cache") / "reports" / "release_manifest.v1.json")],
            summary="Release manifest; release çıktısının “ne üretildi?” özetidir. Eksikse release süreci izlenemez.",
            evidence_expectations=[
                "`.cache/reports/release_manifest.v1.json` mevcut, json_valid ve schema-valid.",
                "Manifest closeout’larda evidence_paths ile referanslanıyor.",
            ],
            remediation=[
                "Release pipeline’ına manifest writer ekle (atomic write + sort_keys).",
                "Manifest için contract test ekle ve single-poll reproof ile kanıtla.",
            ],
        ),
    ]
    return _finalize_findings_v1(items)


def _build_integration_coherence_findings(
    *,
    workspace_root: Path,
    raw_ref: str,
    signals_present: bool,
    thresholds: dict[str, Any],
    warn_cfg: dict[str, Any],
    fail_cfg: dict[str, Any],
    checks: dict[str, int],
) -> dict[str, Any]:
    raw_ref_norm = raw_ref if isinstance(raw_ref, str) and raw_ref.strip() else str(Path(".cache") / "index" / "assessment_raw.v1.json")

    def _resolve_threshold(value: Any) -> float:
        if isinstance(value, str):
            return float(thresholds.get(value, 0) or 0)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _mk_item(
        *,
        key: str,
        base: str,
        title: str,
        topic: str,
        tags: list[str],
        evidence_pointers: list[str],
        summary: str,
        evidence_expectations: list[str],
        remediation: list[str],
    ) -> dict[str, Any]:
        if not signals_present:
            match_status = "UNKNOWN"
            reasons = ["missing_integration_signals"]
        else:
            count_val = int(checks.get(key, 0) or 0)
            reasons = []
            match_status = "NOT_TRIGGERED"
            if key in fail_cfg and count_val > _resolve_threshold(fail_cfg.get(key)):
                match_status = "TRIGGERED"
                reasons = [f"{base}_fail"]
            elif key in warn_cfg and count_val > _resolve_threshold(warn_cfg.get(key)):
                match_status = "TRIGGERED"
                reasons = [f"{base}_warn"]

        all_tags = _normalize_tag_list(
            ["core", "domain_integration", "lens:integration_coherence", f"check:{key}", f"topic:{topic}", *tags]
        )
        evid = {raw_ref_norm}
        for p in evidence_pointers:
            rp = _rel_evidence_pointer(workspace_root, p)
            if rp:
                evid.add(rp)
            elif isinstance(p, str) and p.strip() and not Path(p).is_absolute():
                evid.add(Path(p).as_posix())
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"integration_coherence.{key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set(reasons)),
            "evidence_pointers": sorted(evid),
        }
        if isinstance(summary, str) and summary.strip():
            payload["summary"] = summary.strip()
        if isinstance(evidence_expectations, list):
            ee = [str(x).strip() for x in evidence_expectations if isinstance(x, str) and str(x).strip()]
            if ee:
                payload["evidence_expectations"] = ee
        if isinstance(remediation, list):
            rem = [str(x).strip() for x in remediation if isinstance(x, str) and str(x).strip()]
            if rem:
                payload["remediation"] = rem
        return payload

    items = [
        _mk_item(
            key="layer_boundary_violations_gt",
            base="layer_boundary_violations",
            title="Layer boundary violations",
            topic="baglam_uyum",
            tags=["layer_boundary", "scope"],
            evidence_pointers=[str(Path(".cache") / "reports" / "layer_boundary_report.v1.json")],
            summary="Layer boundary ihlali; core/workspace sınırı aşıldığında drift ve güvenlik riski yükselir.",
            evidence_expectations=[
                "layer_boundary_report ihlalsiz (0) olmalı.",
                "Core editleri sadece CORE_UNLOCK + allowlist+TTL penceresinde yapılmalı.",
            ],
            remediation=[
                "İhlal varsa core/workspace ayrımını düzelt; src/** yazımı penceresini daralt.",
                "Layer-boundary contract test ekle ve fail-closed enforce et.",
            ],
        ),
        _mk_item(
            key="pack_conflicts_gt",
            base="pack_conflicts",
            title="Pack conflicts",
            topic="entegrasyon_birlikte_calisabilirlik",
            tags=["pack_conflicts", "integration"],
            evidence_pointers=[str(Path(".cache") / "index" / "pack_validation_report.json")],
            summary="Pack conflict; paket/manifest uyuşmazlığı entegrasyonu kırar ve ilerlemeyi bloklar.",
            evidence_expectations=[
                "pack_validation_report conflict_count=0 olmalı.",
                "Manifest/pack sürümleri deterministik ve izlenebilir olmalı.",
            ],
            remediation=[
                "Conflict kaynağını belirle: manifest/lock/registry uyuşmazlığı mı?",
                "Paket seçim/lock mekanizmasına contract test ekle.",
            ],
        ),
        _mk_item(
            key="core_unlock_scope_widen_gt",
            base="core_unlock_scope_widen",
            title="Core unlock scope widen",
            topic="uygunluk_risk_guvence_kontrol",
            tags=["core_unlock", "scope"],
            evidence_pointers=[str(Path(".cache") / "reports" / "core_unlock_compliance.v1.json")],
            summary="CORE_UNLOCK scope widen; allowlist’in gereksiz genişlemesi kontrol kaybı ve drift üretir.",
            evidence_expectations=[
                "core_unlock_compliance: allow_paths + ttl_seconds + reason + restore kanıtı mevcut.",
                "ONE_SHOT_SRC_WINDOW dışında src/** yazımı yok.",
            ],
            remediation=[
                "Allowlist’i daralt ve TTL’yi kısa tut; gereksiz yolları çıkar.",
                "Scope widen durumunu otomatik WARN/FAIL olarak raporla.",
            ],
        ),
        _mk_item(
            key="schema_fail_gt",
            base="schema_fail",
            title="Schema validation failures",
            topic="kalite_dogruluk",
            tags=["schema", "validation"],
            evidence_pointers=[str(Path(".cache") / "reports" / "preflight_stamp.v1.json")],
            summary="Schema fail; şema kontratları bozulduğunda lens/ops çıktıları güvenilmez hale gelir.",
            evidence_expectations=[
                "ci/validate_schemas.py PASS.",
                "preflight_stamp içinde schema_validation_summary ok=true.",
            ],
            remediation=[
                "Şemayı güncelle ve validate_schemas geçene kadar fail-closed tut.",
                "Kritik çıktılar için schema+semantic contract test ekle.",
            ],
        ),
    ]
    return _finalize_findings_v1(items)


def _build_operability_findings(
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
    raw_ref_norm = raw_ref if isinstance(raw_ref, str) and raw_ref.strip() else str(Path(".cache") / "index" / "assessment_raw.v1.json")

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
            "remediation": ["airunner jobs index üretimini doğrula; gerekirse jobs poll/tick çalıştır."],
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
        all_tags = _normalize_tag_list(["core", "domain_operability", "lens:operability", f"signal:{key}", f"topic:{topic}"])
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"operability.signal.{key}",
            "title": f"Required signal present: {key}",
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": "NOT_TRIGGERED" if ok else "TRIGGERED",
            "reasons": [] if ok else ["missing_required_signal"],
            "evidence_pointers": sorted(
                set(
                    [
                        raw_ref_norm,
                        str(Path(".cache") / "index" / "assessment_raw.v1.json"),
                    ]
                )
            ),
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
        ("hard_exceeded_gt", "script_budget_present", "maliyet_verimlilik_kaynak", "Script budget hard exceeded", ["script_budget"], "script_budget_report_path"),
        ("soft_exceeded_gt", "script_budget_present", "maliyet_verimlilik_kaynak", "Script budget soft exceeded", ["script_budget"], "script_budget_report_path"),
        ("integrity_fail", "integrity_present", "kalite_dogruluk", "Integrity status FAIL", ["integrity"], "integrity_snapshot_ref"),
        ("jobs_stuck_gt", "airunner_jobs_present", "sureklilik_dayaniklilik", "Jobs stuck", ["jobs"], "airrunner_jobs_index_path"),
        ("jobs_fail_gt", "airunner_jobs_present", "zaman_hiz_ceviklik", "Jobs failed", ["jobs"], "airrunner_jobs_index_path"),
        ("pdca_cursor_stale_hours_gt", "pdca_cursor_present", "surec_etkinligi_olgunluk", "PDCA cursor stale hours", ["pdca"], str(Path(".cache") / "index" / "pdca_cursor.v1.json")),
        ("heartbeat_stale_seconds_gt", "heartbeat_present", "sureklilik_dayaniklilik", "Heartbeat stale seconds", ["heartbeat"], "heartbeat_path"),
        ("placeholders_gt", "doc_nav_present", "gozlemlenebilirlik_izleme_olcme", "Doc-nav placeholders", ["doc_nav"], "doc_nav_report_path"),
        ("docs_ops_md_count_gt", "docs_hygiene_present", "surec_etkinligi_olgunluk", "Docs ops markdown count", ["docs_hygiene"], str(Path(".cache") / "reports" / "repo_hygiene.v1.json")),
        ("docs_ops_md_bytes_gt", "docs_hygiene_present", "surec_etkinligi_olgunluk", "Docs ops markdown bytes", ["docs_hygiene"], str(Path(".cache") / "reports" / "repo_hygiene.v1.json")),
        ("repo_md_total_count_gt", "docs_hygiene_present", "surec_etkinligi_olgunluk", "Repo markdown total count", ["docs_hygiene"], str(Path(".cache") / "reports" / "repo_hygiene.v1.json")),
        ("docs_unmapped_md_gt", "docs_drift_present", "baglam_uyum", "Docs drift unmapped markdown", ["docs_drift"], str(Path(".cache") / "reports" / "docs_drift_signal.v1.json")),
        ("intake_new_items_per_day_gt", "work_intake_present", "surec_etkinligi_olgunluk", "Work intake new items (24h)", ["work_intake"], str(Path(".cache") / "index" / "work_intake.v1.json")),
        ("suppressed_per_day_gt", "work_intake_present", "surec_etkinligi_olgunluk", "Work intake suppressed (24h)", ["work_intake"], str(Path(".cache") / "index" / "work_intake.v1.json")),
    ]

    reason_map = {
        "docs_ops_md_count_gt": "operability_docs_ops_md_count_gt",
        "docs_ops_md_bytes_gt": "operability_docs_ops_md_bytes_gt",
        "repo_md_total_count_gt": "operability_repo_md_total_count_gt",
        "docs_unmapped_md_gt": "operability_docs_unmapped_md_gt",
    }

    def _reason_code(key: str) -> str:
        return reason_map.get(key, key)

    check_items: list[dict[str, Any]] = []
    check_details: dict[str, dict[str, Any]] = {
        "hard_exceeded_gt": {
            "summary": "Hard budget aşıldıysa fail-closed davranılır; bu, kaynak sınırının net ihlalidir.",
            "evidence_expectations": ["hard_exceeded=0 olmalı."],
            "remediation": ["Heavy ops’u azalt/jobify et; gereksiz IO’yu kes; tekrar script-budget al."],
        },
        "soft_exceeded_gt": {
            "summary": "Soft budget aşımı performans/IO baskısı sinyalidir; trend olarak iyileştirilmesi gerekir.",
            "evidence_expectations": ["soft_exceeded düşük/0 olmalı (hedef)."],
            "remediation": ["Refactor ile soft’u düşür; throttle/jobify; gerekirse manual bakım (prune) uygula."],
        },
        "pdca_cursor_stale_hours_gt": {
            "summary": "PDCA cursor stale; sürekli iyileştirme döngüsü güncel değil.",
            "evidence_expectations": ["pdca_cursor stale_hours warn/fail eşik altında olmalı."],
            "remediation": ["pdca-recheck’i cooldown+budget gate ile otomatikleştir veya manuel tetikle."],
        },
        "heartbeat_stale_seconds_gt": {
            "summary": "Heartbeat stale; expectation mode’a göre bu WARN/FAIL olabilir.",
            "evidence_expectations": ["heartbeat stale_seconds warn/fail eşik altında olmalı."],
            "remediation": ["Heartbeat üretim kaynağını doğrula; beklenmiyorsa expectation mode’u ayarla."],
        },
        "placeholders_gt": {
            "summary": "Doc-nav placeholder/broken ref sinyali; doküman kalitesi düşmüş olabilir.",
            "evidence_expectations": ["placeholders/broken refs/orphan_critical düşük olmalı."],
            "remediation": ["doc-nav-check strict çalıştır; placeholder’ları temizle; jobify ile timeout azalt."],
        },
        "repo_md_total_count_gt": {
            "summary": "Repo markdown toplam sayısı eşiği aştı; docs hygiene/paketleme gerekebilir.",
            "evidence_expectations": ["repo_md_total_count warn/fail eşik altında olmalı."],
            "remediation": ["Docs kapsamını netleştir; evidence/ yollarını sayımdan hariç tut (hijyen fix)."],
        },
        "docs_unmapped_md_gt": {
            "summary": "Docs drift: unmapped markdown var; navigasyon/SSOT eşleşmesi eksik.",
            "evidence_expectations": ["unmapped_md_count warn/fail eşik altında olmalı."],
            "remediation": ["Doc-nav mapping/allowlist’i güncelle; orphan kritik kalmasın."],
        },
        "intake_new_items_per_day_gt": {
            "summary": "Intake new items artışı; backlog büyümesi veya gürültü sinyali olabilir.",
            "evidence_expectations": ["new_items_24h warn/fail eşik altında olmalı."],
            "remediation": ["Dedup/timestamp zorunluluğu + bucket refinement ile gürültüyü azalt."],
        },
        "suppressed_per_day_gt": {
            "summary": "Suppress sayısı yüksek; semantik (24h delta vs kümülatif) yanlışsa false-positive üretir.",
            "evidence_expectations": ["suppressed_24h semantiği policy ile hizalı olmalı."],
            "remediation": ["suppressed_24h’yi unique keys / 24h delta mantığına hizala; policy ile birlikte güncelle."],
        },
    }
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


def _load_policy_north_star_eval_lenses(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    from src.benchmark.eval_runner_runtime import _load_policy_north_star_eval_lenses as _impl

    return _impl(core_root=core_root, workspace_root=workspace_root)


def _load_policy_north_star_operability(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    from src.benchmark.eval_runner_runtime import _load_policy_north_star_operability as _impl

    return _impl(core_root=core_root, workspace_root=workspace_root)


def _load_policy_north_star_integration_coherence(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    from src.benchmark.eval_runner_runtime import _load_policy_north_star_integration_coherence as _impl

    return _impl(core_root=core_root, workspace_root=workspace_root)


def _lens_status(score: float, min_ok: float, min_warn: float) -> str:
    from src.benchmark.eval_runner_runtime import _lens_status as _impl

    return _impl(score, min_ok, min_warn)


def _ensure_catalogs(workspace_root: Path, *, allow_write: bool) -> tuple[Path, Path, int, int]:
    from src.benchmark.eval_runner_runtime import _ensure_catalogs as _impl

    return _impl(workspace_root, allow_write=allow_write)


def run_eval(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    from src.benchmark.eval_runner_runtime import run_eval as _impl

    return _impl(workspace_root=workspace_root, dry_run=dry_run)
