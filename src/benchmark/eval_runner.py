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
    defaults = {
        "version": "v1",
        "eval_lenses_enabled": [
            "trend",
            "integrity_compat",
            "integration_coherence",
            "ai_ops_fit",
            "github_ops_release",
            "operability",
        ],
        "trend_best_practice": {"min_coverage_ok": 0.5, "min_coverage_warn": 0.2},
        "integrity_compat": {"min_score_ok": 1.0, "min_score_warn": 0.5},
        "integration_coherence": {
            "weight": 0.2,
            "required_signals": [
                "layer_boundary_report",
                "pack_validation_report",
                "core_unlock_compliance",
                "schema_validation_summary",
            ],
        },
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
                "docs_hygiene_present",
                "docs_drift_present",
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
                "findings": trend_findings,
            },
            "integrity_compat": {
                "status": integrity_lens_status,
                "score": round(float(integrity_score), 4),
                "integrity_status": str(integrity_status or "FAIL"),
                "notes": [],
            },
            "integration_coherence": {
                "status": integration_classification,
                "score": round(float(integration_score), 4),
                "classification": integration_classification,
                "coverage": round(float(integration_coverage), 4),
                "reasons": integration_reasons,
                "findings": integration_findings,
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
                "findings": ai_ops_findings,
            },
            "github_ops_release": {
                "status": gh_status,
                "score": round(float(gh_score), 4),
                "coverage": round(float(gh_score), 4),
                "requirements": gh_requirements,
                "notes": gh_notes,
                "findings": gh_ops_findings,
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
                "findings": operability_findings,
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
