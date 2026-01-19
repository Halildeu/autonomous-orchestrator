from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import _extract_domains_from_tags, _finalize_findings_v1, _normalize_tag_list


def _build_ai_ops_fit_findings_impl(
    *,
    workspace_root: Path,
    raw_ref: str,
    requirements: dict[str, bool],
) -> dict[str, Any]:
    raw_ref_norm = (
        raw_ref
        if isinstance(raw_ref, str) and raw_ref.strip()
        else str(Path(".cache") / "index" / "assessment_raw.v1.json")
    )
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
        all_tags = _normalize_tag_list(
            ["core", "domain_ai", "lens:ai_ops_fit", f"requirement:{key}", f"topic:{topic}", *tags]
        )
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"ai_ops_fit.{key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set([] if ok else reasons_triggered)),
            "evidence_pointers": sorted(
                set([raw_ref_norm, *[p for p in evidence_pointers if isinstance(p, str) and p.strip()]])
            ),
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

