from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import _extract_domains_from_tags, _finalize_findings_v1, _normalize_tag_list


def _build_github_ops_release_findings_impl(
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

