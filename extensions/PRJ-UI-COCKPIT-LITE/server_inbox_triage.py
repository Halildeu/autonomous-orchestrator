from __future__ import annotations

from datetime import datetime, timezone

# NOTE: This module is imported lazily from server_utils to avoid import-time cycles.
# It intentionally pulls shared helpers from server_utils via star-import (scoped by server_utils.__all__).
from server_utils import *  # noqa: F403


def _inbox_triage_apply_ai(ws_root: Path, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if payload.get("confirm") is not True:
        return 400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"}

    mode = str(payload.get("mode") or "new_manual_request").strip()
    try:
        limit = int(payload.get("limit") or 200)
    except Exception:
        limit = 200
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    if mode not in {"new_manual_request", "apply_ai"}:
        return 400, {"status": "FAIL", "error": "MODE_INVALID"}

    inbox_path = ws_root / ".cache" / "index" / "input_inbox.v0.1.json"
    inbox_obj, inbox_exists, inbox_valid = _read_json_file(inbox_path)
    if not inbox_exists or not inbox_valid or not isinstance(inbox_obj, dict):
        return 409, {"status": "FAIL", "error": "INBOX_INDEX_UNAVAILABLE"}
    inbox_items = inbox_obj.get("items")
    inbox_list = inbox_items if isinstance(inbox_items, list) else []

    triage_path = ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json"
    triage_obj, triage_exists, triage_valid = _read_json_file(triage_path)
    triage_data: dict[str, Any]
    if triage_exists and triage_valid and isinstance(triage_obj, dict):
        triage_data = triage_obj
    else:
        triage_data = {"generated_at": "", "items": []}

    triage_items = triage_data.get("items")
    triage_list = triage_items if isinstance(triage_items, list) else []
    triage_data["items"] = triage_list

    entry_map: dict[str, dict[str, Any]] = {}
    for it in triage_list:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("request_id") or "").strip()
        if rid:
            entry_map[rid] = it

    def _inbox_text_blob(item: dict[str, Any]) -> str:
        intake = item.get("intake") if isinstance(item.get("intake"), dict) else {}
        suggested = item.get("suggested_route") if isinstance(item.get("suggested_route"), dict) else {}
        tags = suggested.get("tags")
        tags_text = " ".join([str(x) for x in tags]) if isinstance(tags, list) else str(tags or "")
        parts = [
            item.get("request_id"),
            item.get("artifact_type"),
            item.get("kind"),
            item.get("domain"),
            item.get("impact_scope"),
            suggested.get("bucket"),
            suggested.get("reason"),
            tags_text,
            intake.get("title"),
            intake.get("bucket"),
            intake.get("status"),
            intake.get("closed_reason"),
            item.get("text_preview"),
        ]
        return " ".join([str(p).strip() for p in parts if str(p or "").strip()]).lower()

    def _suggest_owner_project(item: dict[str, Any]) -> str:
        text = _inbox_text_blob(item)
        if not text:
            return ""
        if "work-intake" in text or "work intake" in text or "context-router" in text:
            return "PRJ-WORK-INTAKE"
        if "airunner" in text or "heartbeat" in text or "doer-loop" in text:
            return "PRJ-AIRUNNER"
        if "pm-suite" in text or "portfolio" in text or "roadmap" in text:
            return "PRJ-PM-SUITE"
        if "cockpit" in text:
            return "PRJ-UI-COCKPIT-LITE"
        return ""

    def _suggest_ai_update(item: dict[str, Any]) -> dict[str, Any] | None:
        intake = item.get("intake") if isinstance(item.get("intake"), dict) else {}
        suggested = item.get("suggested_route") if isinstance(item.get("suggested_route"), dict) else {}
        suggested_bucket = str(suggested.get("bucket") or intake.get("bucket") or "").strip().upper()
        suggested_reason = str(suggested.get("reason") or "").strip()
        intake_status = str(intake.get("status") or "").strip().upper()
        closed_reason = str(intake.get("closed_reason") or "").strip().upper()
        requires_core = bool(item.get("requires_core_change"))

        if intake_status == "DONE":
            reason = f" ({closed_reason})" if closed_reason else ""
            return {
                "state": "DISMISSED",
                "classification": {"route_bucket": "TICKET"},
                "rationale": f"AI: intake DONE{reason}; dismiss",
            }
        if requires_core or suggested_bucket == "ROADMAP":
            return {
                "state": "ROUTE_TO_ROADMAP",
                "classification": {"route_bucket": "ROADMAP"},
                "rationale": f"AI: ROADMAP ({suggested_reason})" if suggested_reason else "AI: ROADMAP",
            }
        if suggested_bucket == "PROJECT":
            owner = _suggest_owner_project(item)
            classification = {"route_bucket": "PROJECT"}
            if owner:
                classification["owner_project"] = owner
            return {
                "state": "ROUTE_TO_PROJECT",
                "classification": classification,
                "rationale": f"AI: PROJECT ({suggested_reason})" if suggested_reason else "AI: PROJECT",
            }
        if suggested_bucket == "TICKET" and intake_status == "OPEN":
            return {
                "state": "ROUTE_TO_TICKET",
                "classification": {"route_bucket": "TICKET"},
                "rationale": "AI: keep as ticket",
            }
        return None

    allowed_states = {
        "NEW",
        "NEEDS_INFO",
        "DISMISSED",
        "ROUTE_TO_TICKET",
        "ROUTE_TO_ROADMAP",
        "ROUTE_TO_PROJECT",
        "CONVERT_TO_PROJECT",
    }
    allowed_classification_keys = {
        "route_bucket",
        "theme_id",
        "milestone",
        "milestone_id",
        "owner_project",
        "project_id",
        "decision",
    }

    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    applied: list[dict[str, Any]] = []
    skipped = 0

    for source_item in inbox_list:
        if not isinstance(source_item, dict):
            continue
        evidence_path = str(source_item.get("evidence_path") or "").strip()
        if not evidence_path:
            continue
        if not evidence_path.startswith(".cache/index/manual_requests/") and "/.cache/index/manual_requests/" not in evidence_path:
            continue

        request_id = str(source_item.get("request_id") or "").strip()
        if not request_id:
            continue

        existing_entry = entry_map.get(request_id)
        current_state = str(existing_entry.get("state") or "").strip().upper() if isinstance(existing_entry, dict) else "NEW"
        if current_state and current_state != "NEW":
            continue

        suggestion = _suggest_ai_update(source_item)
        if not suggestion:
            skipped += 1
            continue

        state_value = str(suggestion.get("state") or "").strip().upper()
        if state_value not in allowed_states:
            skipped += 1
            continue

        classification_raw = suggestion.get("classification")
        classification_raw = classification_raw if isinstance(classification_raw, dict) else {}
        classification: dict[str, str] = {}
        for key, value in classification_raw.items():
            k = str(key or "").strip()
            if not k:
                continue
            if k not in allowed_classification_keys:
                continue
            v = str(value or "").strip()
            if not v:
                continue
            if len(v) > 240:
                continue
            classification[k] = v

        expected_bucket = None
        if state_value == "ROUTE_TO_ROADMAP":
            expected_bucket = "ROADMAP"
        elif state_value in {"ROUTE_TO_PROJECT", "CONVERT_TO_PROJECT"}:
            expected_bucket = "PROJECT"
        elif state_value in {"ROUTE_TO_TICKET", "DISMISSED"}:
            expected_bucket = "TICKET"

        if expected_bucket:
            if "route_bucket" not in classification:
                classification["route_bucket"] = expected_bucket
            elif str(classification.get("route_bucket") or "").upper() != expected_bucket:
                skipped += 1
                continue

        intake = source_item.get("intake") if isinstance(source_item.get("intake"), dict) else {}
        intake_id = str(intake.get("intake_id") or "").strip()

        links: dict[str, Any] = {}
        if existing_entry and isinstance(existing_entry.get("links"), dict):
            links = dict(existing_entry.get("links") or {})
        if evidence_path:
            links.setdefault("evidence_path", evidence_path)
        if intake_id:
            links.setdefault("intake_id", intake_id)

        new_entry = {
            "request_id": request_id,
            "state": state_value,
            "rationale": str(suggestion.get("rationale") or "").strip(),
            "classification": classification,
            "updated_at": updated_at,
            "links": links,
        }
        if existing_entry is None:
            triage_list.append(new_entry)
            entry_map[request_id] = new_entry
        else:
            existing_entry.clear()
            existing_entry.update(new_entry)

        applied.append({"request_id": request_id, "state": state_value})
        if len(applied) >= limit:
            break

    if not applied:
        trace_meta = _trace_meta_for_op(
            "inbox-triage-apply-ai",
            {"mode": mode, "applied_count": 0, "skipped_count": skipped},
            ws_root,
        )
        return (
            200,
            {
                "status": "WARN",
                "op": "inbox-triage-apply-ai",
                "error": "NOTHING_TO_APPLY",
                "mode": mode,
                "skipped_count": skipped,
                "trace_meta": trace_meta,
                "evidence_paths": [str(triage_path)],
            },
        )

    triage_data["generated_at"] = updated_at
    _atomic_write_text(triage_path, json.dumps(triage_data, ensure_ascii=False, indent=2) + "\n")

    trace_meta = _trace_meta_for_op(
        "inbox-triage-apply-ai",
        {"mode": mode, "applied_count": len(applied), "skipped_count": skipped},
        ws_root,
    )
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _chat_append(
        ws_root,
        {
            "version": "v1",
            "type": "OP_CALL",
            "ts": ts,
            "op": "inbox-triage-apply-ai",
            "args": _redact({"mode": mode, "applied_count": len(applied), "skipped_count": skipped}),
            "trace_meta": trace_meta,
            "evidence_paths": [str(triage_path)],
        },
    )
    _chat_append(
        ws_root,
        {
            "version": "v1",
            "type": "RESULT",
            "ts": ts,
            "op": "inbox-triage-apply-ai",
            "status": "OK",
            "trace_meta": trace_meta,
            "evidence_paths": [str(triage_path)],
        },
    )

    return (
        200,
        {
            "status": "OK",
            "op": "inbox-triage-apply-ai",
            "mode": mode,
            "applied_count": len(applied),
            "skipped_count": skipped,
            "applied": applied[:50],
            "trace_meta": trace_meta,
            "evidence_paths": [str(triage_path)],
        },
    )

