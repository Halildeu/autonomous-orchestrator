from __future__ import annotations

from typing import Any

OPERABILITY_REASON_MAP_V1: dict[str, str] = {
    "docs_ops_md_count_gt": "operability_docs_ops_md_count_gt",
    "docs_ops_md_bytes_gt": "operability_docs_ops_md_bytes_gt",
    "repo_md_total_count_gt": "operability_repo_md_total_count_gt",
    "docs_unmapped_md_gt": "operability_docs_unmapped_md_gt",
}

OPERABILITY_CHECK_DETAILS_V1: dict[str, dict[str, Any]] = {
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
