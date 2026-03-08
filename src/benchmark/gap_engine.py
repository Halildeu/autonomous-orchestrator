from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


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
    previous_gap_register: dict[str, Any] | None = None,
    cooldown_seconds: int = 0,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    seen_gap_ids: set[str] = set()
    previous_gap_ids: set[str] = set()
    previous_generated_at = None
    if isinstance(previous_gap_register, dict):
        previous_generated_at = _parse_iso(previous_gap_register.get("generated_at"))
        prev_gaps = previous_gap_register.get("gaps")
        if isinstance(prev_gaps, list):
            for g in prev_gaps:
                gap_id = g.get("id") if isinstance(g, dict) else None
                if isinstance(gap_id, str) and gap_id:
                    previous_gap_ids.add(gap_id)

    def _cooldown_active(gap_id: str) -> bool:
        if not gap_id or not previous_gap_ids or cooldown_seconds <= 0:
            return False
        if gap_id not in previous_gap_ids:
            return False
        if previous_generated_at is None:
            return False
        delta = datetime.now(timezone.utc) - previous_generated_at
        return delta.total_seconds() < float(cooldown_seconds)
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

    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

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
        docs_hygiene_reasons = {
            "operability_docs_ops_md_count_gt",
            "operability_docs_ops_md_bytes_gt",
            "operability_repo_md_total_count_gt",
        }
        window_hash = source_eval_hash or source_raw_hash or "0"
        if lens_id == "operability" and reason_code == "operability_docs_unmapped_md_gt":
            gap_id = "GAP-EVAL-LENS-operability-docs_unmapped_md_gt"
        elif lens_id == "operability" and reason_code in docs_hygiene_reasons:
            digest = _hash_text(f"operability{reason_code}{window_hash}")
            gap_id = f"GAP-EVAL-LENS-operability-docs-{digest}"
        else:
            gap_id = f"GAP-EVAL-LENS-{lens_id}" + (f"-{reason_code}" if reason_code else "")
        gap = {
            "id": gap_id,
            "metric_id": f"eval_lens:{lens_id}" + (f":{reason_code}" if reason_code else ""),
            "severity": severity,
            "risk_class": _risk_class(severity),
            "effort": _default_effort(),
            "status": "open",
            "notes": notes,
        }
        if _cooldown_active(gap_id):
            gap["update_only"] = True
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

    def _append_gap(gap: dict[str, Any] | None) -> None:
        if not isinstance(gap, dict):
            return
        gap_id = gap.get("id")
        if not isinstance(gap_id, str) or not gap_id:
            return
        if gap_id in seen_gap_ids:
            return
        seen_gap_ids.add(gap_id)
        gaps.append(gap)

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
        _append_gap(gap)
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
        _append_gap(gap)
    if isinstance(lens_signals, list):
        for lens in lens_signals:
            if not isinstance(lens, dict):
                continue
            reasons_raw = lens.get("reasons")
            reasons = [str(x).strip() for x in reasons_raw if isinstance(x, str) and str(x).strip()] if isinstance(
                reasons_raw, list
            ) else []
            if reasons:
                for reason in reasons:
                    _append_gap(_lens_gap(lens, reason))
                continue
            _append_gap(_lens_gap(lens))
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "gaps": gaps,
    }


def apply_gap_closeout(
    *,
    gap_register: dict[str, Any],
    work_intake: dict[str, Any] | None,
    evidence_pointer: str | None = None,
) -> dict[str, Any]:
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    items = work_intake.get("items") if isinstance(work_intake, dict) else None
    if not isinstance(gaps, list) or not isinstance(items, list):
        return gap_register

    closed_gaps: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_type") or "") != "GAP":
            continue
        if str(item.get("status") or "") != "DONE":
            continue
        gap_id = str(item.get("source_ref") or "").strip()
        if not gap_id:
            continue
        closed_reason = str(item.get("closed_reason") or "").strip() or "DONE"
        closed_gaps[gap_id] = closed_reason

    if not closed_gaps:
        return gap_register

    updated_gaps: list[dict[str, Any]] = []
    changed = False
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        gap_id = str(gap.get("id") or "").strip()
        closed_reason = closed_gaps.get(gap_id)
        if not closed_reason:
            updated_gaps.append(dict(gap))
            continue
        changed = True
        updated_gap = dict(gap)
        updated_gap["status"] = "closed"
        close_note = f"Closed via work_intake: {closed_reason}."
        existing_note = str(gap.get("notes") or "").strip()
        if existing_note and existing_note != "Assessment not yet completed." and close_note not in existing_note:
            updated_gap["notes"] = f"{existing_note} {close_note}".strip()
        else:
            updated_gap["notes"] = close_note
        evidence = gap.get("evidence_pointers") if isinstance(gap.get("evidence_pointers"), list) else []
        evidence_paths = [str(p).strip() for p in evidence if isinstance(p, str) and str(p).strip()]
        if evidence_pointer and evidence_pointer not in evidence_paths:
            evidence_paths.append(evidence_pointer)
        if evidence_paths:
            updated_gap["evidence_pointers"] = sorted(set(evidence_paths))
        updated_gaps.append(updated_gap)

    if not changed:
        return gap_register

    payload = dict(gap_register)
    payload["gaps"] = updated_gaps
    return payload


def build_gap_summary_md(*, gap_register: dict[str, Any]) -> str:
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    total = len(gaps) if isinstance(gaps, list) else 0
    lens_gaps = 0
    if isinstance(gaps, list):
        for item in gaps:
            gap_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(gap_id, str) and gap_id.startswith("GAP-EVAL-LENS-"):
                lens_gaps += 1
    return "\n".join(
        [
            "# Gap Summary",
            "",
            f"Total gaps: {total}",
            f"Lens-triggered gaps: {lens_gaps}",
            "",
            "Notes:",
            "- Control/metric gaps are placeholders until assessments are completed.",
            "- Lens-triggered gaps are derived from assessment_eval lens statuses.",
        ]
    ) + "\n"
