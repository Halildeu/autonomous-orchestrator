from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import (
    _extract_domains_from_tags,
    _finalize_findings_v1,
    _normalize_tag_list,
    _rel_evidence_pointer,
)


def _build_integration_coherence_findings_impl(
    *,
    workspace_root: Path,
    raw_ref: str,
    signals_present: bool,
    thresholds: dict[str, Any],
    warn_cfg: dict[str, Any],
    fail_cfg: dict[str, Any],
    checks: dict[str, int],
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

