from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(s: str, limit: int = 160) -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 3)] + "..."


def _sanitize_message(msg: str) -> str:
    cleaned = " ".join(msg.split())
    return _truncate(cleaned, 160)


def _clamp_limit(v: Any, *, default: int = 10, min_v: int = 1, max_v: int = 100) -> int:
    try:
        n = int(v)
    except Exception:
        return default
    if n < min_v:
        return min_v
    if n > max_v:
        return max_v
    return n


def _coerce_str(v: Any) -> str:
    return v.strip() if isinstance(v, str) and v.strip() else ""


def run_dlq_triage(envelope: dict[str, Any], workspace: str) -> dict[str, Any]:
    ws = Path(workspace).resolve()
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}

    limit_used = _clamp_limit(context.get("limit"), default=10, min_v=1, max_v=100)
    dlq_dir = ws / "dlq"

    dlq_files: list[Path] = []
    if dlq_dir.exists():
        dlq_files = [p for p in dlq_dir.glob("*.json") if p.is_file()]
    dlq_files.sort(key=lambda p: p.name, reverse=True)

    selected = dlq_files[:limit_used]

    stage_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    message_counts: Counter[str] = Counter()
    items: list[dict[str, str]] = []
    parse_errors = 0

    for p in selected:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            parse_errors += 1
            continue
        if not isinstance(raw, dict):
            parse_errors += 1
            continue

        stage = _coerce_str(raw.get("stage"))
        error_code = _coerce_str(raw.get("error_code"))
        ts = _coerce_str(raw.get("ts"))
        message_raw = raw.get("message")
        message = _sanitize_message(message_raw) if isinstance(message_raw, str) and message_raw.strip() else ""

        stage_counts[stage or "UNKNOWN"] += 1
        error_counts[error_code or "UNKNOWN"] += 1
        if message:
            message_counts[message] += 1

        env_obj = raw.get("envelope")
        request_id = ""
        intent = ""
        if isinstance(env_obj, dict):
            request_id = _coerce_str(env_obj.get("request_id"))
            intent = _coerce_str(env_obj.get("intent"))

        items.append(
            {
                "file": p.name,
                "stage": stage or "UNKNOWN",
                "error_code": error_code or "UNKNOWN",
                "request_id": request_id,
                "intent": intent,
                "ts": ts,
                "message": message,
            }
        )

    items_scanned = len(items)

    counts_by_stage = {k: int(stage_counts[k]) for k in sorted(stage_counts)}
    counts_by_error_code = {k: int(error_counts[k]) for k in sorted(error_counts)}

    top_messages = sorted(message_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    tenant_id = _coerce_str(envelope.get("tenant_id"))
    intent_root = _coerce_str(envelope.get("intent"))

    lines: list[str] = []
    lines.append("# DLQ Triage Report")
    lines.append("")
    lines.append(f"- generated_at: {_now_iso()}")
    if tenant_id:
        lines.append(f"- tenant_id: {tenant_id}")
    if intent_root:
        lines.append(f"- intent: {intent_root}")
    lines.append(f"- limit_used: {limit_used}")
    lines.append(f"- items_scanned: {items_scanned}")
    if parse_errors:
        lines.append(f"- parse_errors: {parse_errors}")
    lines.append("")

    lines.append("## Summary (by stage)")
    if counts_by_stage:
        for k in sorted(counts_by_stage):
            lines.append(f"- {k}: {counts_by_stage[k]}")
    else:
        lines.append("- (no items)")
    lines.append("")

    lines.append("## Summary (by error_code)")
    if counts_by_error_code:
        for k in sorted(counts_by_error_code):
            lines.append(f"- {k}: {counts_by_error_code[k]}")
    else:
        lines.append("- (no items)")
    lines.append("")

    lines.append("## Top messages (sanitized)")
    if top_messages:
        for msg, n in top_messages:
            lines.append(f"- {msg} (x{n})")
    else:
        lines.append("- (no messages)")
    lines.append("")

    lines.append("## Most recent items")
    lines.append("")
    lines.append("| file | stage | error_code | request_id | intent | ts |")
    lines.append("|---|---|---|---|---|---|")
    for it in items[:10]:
        file = it.get("file", "")
        stage = it.get("stage", "")
        error_code = it.get("error_code", "")
        request_id = it.get("request_id", "")
        intent = it.get("intent", "")
        ts = it.get("ts", "")
        lines.append(f"| {file} | {stage} | {error_code} | {request_id} | {intent} | {ts} |")

    report_markdown = "\n".join(lines).rstrip() + "\n"
    report_bytes = len(report_markdown.encode("utf-8"))

    return {
        "status": "OK",
        "items_scanned": int(items_scanned),
        "limit_used": int(limit_used),
        "counts_by_stage": counts_by_stage,
        "counts_by_error_code": counts_by_error_code,
        "report_bytes": int(report_bytes),
        "report_markdown": report_markdown,
    }
