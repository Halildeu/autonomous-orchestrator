from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_context_router_section(workspace_root: Path) -> dict[str, Any] | None:
    router_path = workspace_root / ".cache" / "reports" / "context_pack_router_result.v1.json"
    if not router_path.exists():
        return None
    rel_path = str(Path(".cache") / "reports" / "context_pack_router_result.v1.json")
    try:
        router_obj = _load_json(router_path)
    except Exception:
        router_obj = {}
    status = router_obj.get("status") if isinstance(router_obj, dict) else None
    status_str = status if status in {"OK", "WARN", "IDLE"} else "WARN"
    request_id = router_obj.get("request_id") if isinstance(router_obj.get("request_id"), str) else ""
    context_pack_id = router_obj.get("context_pack_id") if isinstance(router_obj.get("context_pack_id"), str) else ""

    counts_by_bucket = {"ROADMAP": 0, "PROJECT": 0, "TICKET": 0, "INCIDENT": 0}
    top_next_actions: list[dict[str, Any]] = []
    next_focus = "NONE"
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if intake_path.exists():
        try:
            intake_obj = _load_json(intake_path)
        except Exception:
            intake_obj = {}
        items = intake_obj.get("items") if isinstance(intake_obj, dict) else []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("source_type")) != "MANUAL_REQUEST":
                    continue
                bucket = item.get("bucket")
                if bucket in counts_by_bucket:
                    counts_by_bucket[bucket] += 1
        summary = intake_obj.get("summary") if isinstance(intake_obj, dict) else {}
        if isinstance(summary, dict):
            raw_top = summary.get("top_next_actions") if isinstance(summary.get("top_next_actions"), list) else []
            if isinstance(raw_top, list):
                for item in raw_top[:5]:
                    if not isinstance(item, dict):
                        continue
                    top_next_actions.append(
                        {
                            "intake_id": item.get("intake_id"),
                            "bucket": item.get("bucket"),
                            "severity": item.get("severity"),
                            "priority": item.get("priority"),
                            "title": item.get("title"),
                        }
                    )
            next_focus = summary.get("next_intake_focus") if isinstance(summary.get("next_intake_focus"), str) else "NONE"

    return {
        "status": status_str,
        "last_request_id": request_id,
        "last_context_pack_id": context_pack_id,
        "last_router_result_path": rel_path,
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions[:5],
        "next_focus": next_focus,
    }


def context_router_md_lines(context_router: dict[str, Any]) -> list[str]:
    lines = [
        f"Status: {context_router.get('status', '')}",
        f"Last request: {context_router.get('last_request_id', '')}",
        f"Last context pack: {context_router.get('last_context_pack_id', '')}",
        f"Next focus: {context_router.get('next_focus', '')}",
    ]
    counts = context_router.get("counts_by_bucket") if isinstance(context_router, dict) else None
    if isinstance(counts, dict):
        lines.append(
            "Manual requests by bucket: "
            + ", ".join(f"{k}={counts.get(k, 0)}" for k in ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"])
        )
    top_actions = context_router.get("top_next_actions") if isinstance(context_router, dict) else None
    if isinstance(top_actions, list) and top_actions:
        lines.append("Top next:")
        for item in top_actions[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('intake_id', '')} bucket={item.get('bucket', '')} "
                f"severity={item.get('severity', '')} priority={item.get('priority', '')}"
            )
    return lines
