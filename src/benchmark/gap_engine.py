from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_gap_register(
    *,
    controls: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    lens_signals: list[dict[str, Any]] | None = None,
    integrity_snapshot_ref: str | None = None,
    source_eval_hash: str | None = None,
    source_raw_hash: str | None = None,
    evidence_pointers: list[str] | None = None,
    report_only: bool = False,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    def _risk_class(severity: str) -> str:
        return severity if severity in {"low", "medium", "high"} else "medium"

    def _default_effort() -> str:
        return "medium"

    def _normalize_reason(value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return "unknown"
        cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw)
        return cleaned.strip("_") or "unknown"

    def _lens_gap(lens: dict[str, Any], reason: str | None = None) -> dict[str, Any] | None:
        lens_id = lens.get("lens_id") or lens.get("id")
        if not isinstance(lens_id, str) or not lens_id:
            return None
        status = str(lens.get("status") or "").upper()
        if status == "OK" or not status:
            return None
        severity = "high" if status == "FAIL" else "medium"
        score = lens.get("score")
        notes = f"Eval lens {lens_id} status {status}."
        if isinstance(score, (int, float)):
            notes = f"{notes} score={round(float(score), 4)}"
        reason_code = _normalize_reason(reason) if isinstance(reason, str) and reason.strip() else ""
        gap = {
            "id": f"GAP-EVAL-LENS-{lens_id}" + (f"-{reason_code}" if reason_code else ""),
            "metric_id": f"eval_lens:{lens_id}" + (f":{reason_code}" if reason_code else ""),
            "severity": severity,
            "risk_class": _risk_class(severity),
            "effort": _default_effort(),
            "status": "open",
            "notes": notes,
        }
        if integrity_snapshot_ref:
            gap["integrity_snapshot_ref"] = integrity_snapshot_ref
        if source_eval_hash:
            gap["source_eval_hash"] = source_eval_hash
        if source_raw_hash:
            gap["source_raw_hash"] = source_raw_hash
        if evidence_pointers:
            gap["evidence_pointers"] = list(evidence_pointers)
        if report_only:
            gap["report_only"] = True
        return gap

    for c in sorted(controls, key=lambda x: str(x.get("id") or "")):
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not cid:
            continue
        severity = "medium"
        gap = {
            "id": f"GAP-{cid}",
            "control_id": cid,
            "severity": severity,
            "risk_class": _risk_class(severity),
            "effort": _default_effort(),
            "status": "open",
            "notes": "Assessment not yet completed.",
        }
        if integrity_snapshot_ref:
            gap["integrity_snapshot_ref"] = integrity_snapshot_ref
        if source_eval_hash:
            gap["source_eval_hash"] = source_eval_hash
        if source_raw_hash:
            gap["source_raw_hash"] = source_raw_hash
        if evidence_pointers:
            gap["evidence_pointers"] = list(evidence_pointers)
        if report_only:
            gap["report_only"] = True
        gaps.append(gap)
    for m in sorted(metrics, key=lambda x: str(x.get("id") or "")):
        mid = m.get("id") if isinstance(m, dict) else None
        if not isinstance(mid, str) or not mid:
            continue
        severity = "low"
        gap = {
            "id": f"GAP-{mid}",
            "metric_id": mid,
            "severity": severity,
            "risk_class": _risk_class(severity),
            "effort": _default_effort(),
            "status": "open",
            "notes": "Assessment not yet completed.",
        }
        if integrity_snapshot_ref:
            gap["integrity_snapshot_ref"] = integrity_snapshot_ref
        if source_eval_hash:
            gap["source_eval_hash"] = source_eval_hash
        if source_raw_hash:
            gap["source_raw_hash"] = source_raw_hash
        if evidence_pointers:
            gap["evidence_pointers"] = list(evidence_pointers)
        if report_only:
            gap["report_only"] = True
        gaps.append(gap)
    if lens_signals:
        for lens in sorted(
            [l for l in lens_signals if isinstance(l, dict)],
            key=lambda l: str(l.get("lens_id") or l.get("id") or ""),
        ):
            reasons = lens.get("reasons") if isinstance(lens.get("reasons"), list) else []
            reason_list = [str(r) for r in reasons if isinstance(r, str) and r.strip()]
            if reason_list:
                for reason in sorted(set(reason_list)):
                    gap = _lens_gap(lens, reason=reason)
                    if gap is not None:
                        gaps.append(gap)
                continue
            gap = _lens_gap(lens)
            if gap is not None:
                gaps.append(gap)
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "gaps": gaps,
    }


def build_gap_summary_md(*, gap_register: dict[str, Any]) -> str:
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    total = len(gaps) if isinstance(gaps, list) else 0
    return "\n".join(
        [
            "# Gap Summary",
            "",
            f"Total gaps: {total}",
            "",
            "Notes:",
            "- Gaps are placeholders until assessments are completed.",
        ]
    ) + "\n"
