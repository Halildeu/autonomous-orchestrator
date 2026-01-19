from __future__ import annotations

from pathlib import Path
from typing import Any

from src.benchmark.eval_runner import (
    _extract_domains_from_tags,
    _finalize_findings_v1,
    _normalize_tag_list,
    _rel_evidence_pointer,
)


def _build_integrity_compat_findings_impl(
    *,
    workspace_root: Path,
    raw_ref: str,
    integrity_snapshot_ref: str,
    integrity_status: str | None,
) -> dict[str, Any]:
    raw_ref_norm = (
        raw_ref
        if isinstance(raw_ref, str) and raw_ref.strip()
        else str(Path(".cache") / "index" / "assessment_raw.v1.json")
    )
    integrity_ref_norm = (
        integrity_snapshot_ref
        if isinstance(integrity_snapshot_ref, str) and integrity_snapshot_ref.strip()
        else str(Path(".cache") / "reports" / "integrity_verify.v1.json")
    )
    integrity_ptr = _rel_evidence_pointer(workspace_root, integrity_ref_norm) or integrity_ref_norm

    integrity_path = workspace_root / integrity_ptr
    snapshot_present = bool(integrity_path.exists())

    status_norm = str(integrity_status or "FAIL").strip().upper()
    if status_norm not in {"PASS", "WARN", "FAIL"}:
        status_norm = "FAIL"

    def _item(
        *,
        key: str,
        title: str,
        topic: str,
        tags: list[str],
        match_status: str,
        reasons: list[str],
        summary: str,
        evidence_expectations: list[str],
        remediation: list[str],
    ) -> dict[str, Any]:
        all_tags = _normalize_tag_list(
            [
                "core",
                "domain_integrity",
                "lens:integrity_compat",
                f"check:{key}",
                f"topic:{topic}",
                *tags,
            ]
        )
        payload: dict[str, Any] = {
            "catalog": "lens",
            "id": f"integrity_compat.{key}",
            "title": title,
            "tags": all_tags,
            "domains": _extract_domains_from_tags(all_tags),
            "topic": topic,
            "match_status": match_status,
            "reasons": sorted(set([str(x) for x in reasons if isinstance(x, str) and str(x).strip()])),
            "evidence_pointers": sorted(set([raw_ref_norm, integrity_ptr])),
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

    items: list[dict[str, Any]] = []
    items.append(
        _item(
            key="integrity_snapshot_present",
            title="Integrity snapshot present",
            topic="uygunluk_risk_guvence_kontrol",
            tags=["integrity", "snapshot"],
            match_status="NOT_TRIGGERED" if snapshot_present else "TRIGGERED",
            reasons=[] if snapshot_present else ["integrity_snapshot_missing"],
            summary="North Star, değerlendirmeyi (raw/eval) bir “integrity snapshot” ile kanıt zincirine bağlar. Snapshot yoksa sonuç güvenilir değildir.",
            evidence_expectations=[
                "`.cache/reports/integrity_verify.v1.json` mevcut olmalı (veya `integrity_snapshot_ref` ile işaretlenen dosya).",
                "Snapshot şema-valid ve parse edilebilir olmalı.",
            ],
            remediation=[
                "Integrity verify/producer op’unu çalıştırıp snapshot üret (no-network).",
                "Üretilen snapshot path’ini `assessment_raw.v1.json` içine referansla (deterministik).",
            ],
        )
    )

    if status_norm == "PASS":
        match_status = "NOT_TRIGGERED"
        reasons = []
    elif status_norm == "WARN":
        match_status = "TRIGGERED"
        reasons = ["integrity_verify_warn"]
    else:
        match_status = "TRIGGERED"
        reasons = ["integrity_verify_fail"]

    items.append(
        _item(
            key="integrity_verify_status",
            title="Integrity verify result (verify_on_read)",
            topic="deterministiklik_tekrarlanabilirlik",
            tags=["integrity", "verify_on_read"],
            match_status=match_status,
            reasons=reasons,
            summary="Integrity verify sonucu `PASS/WARN/FAIL` olmalı. WARN/FAIL, kanıt zincirinde sapma veya uyumsuzluk olabileceğini gösterir.",
            evidence_expectations=[
                "`integrity_verify.v1.json` içinde `verify_on_read_result` alanı PASS olmalı (tercihen).",
                "WARN ise nedenler raporda açıkça listelenmeli; FAIL ise report_only/policy davranışı net olmalı.",
            ],
            remediation=[
                "Integritiy check’in fail nedeni (schema drift, missing artefact, boundary mismatch) için hedefli fix uygula.",
                "Fix sonrası `benchmark-assess` ile re-eval yap ve `integrity_compat` lensini tekrar doğrula.",
            ],
        )
    )

    return _finalize_findings_v1(items)

