from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_gap_register(*, controls: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    def _risk_class(severity: str) -> str:
        return severity if severity in {"low", "medium", "high"} else "medium"

    def _default_effort() -> str:
        return "medium"

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
