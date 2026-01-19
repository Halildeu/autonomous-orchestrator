from __future__ import annotations

from typing import Any


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
    if {"privacy", "pii", "secret", "secrets"} & tag_set:
        return "gizlilik"
    if "security" in tag_set:
        return "guvenlik"
    if {"policy", "compliance", "gates"} & tag_set:
        return "uygunluk_risk_guvence_kontrol"
    if {"triage", "ops", "pipeline"} & tag_set:
        return "surec_etkinligi_olgunluk"
    if {"intake", "stale", "pdca", "gaps"} & tag_set:
        return "surec_etkinligi_olgunluk"
    if "offline" in tag_set or "seed" in tag_set:
        return "surec_etkinligi_olgunluk"
    return ""

