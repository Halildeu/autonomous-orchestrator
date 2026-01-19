from __future__ import annotations

from typing import Any


def _finalize_findings_v1_impl(items: list[dict[str, Any]]) -> dict[str, Any]:
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

