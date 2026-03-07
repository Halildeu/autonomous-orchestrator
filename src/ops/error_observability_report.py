from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ERROR_OBSERVABILITY_REPORT = Path(".cache") / "reports" / "error_observability.v1.json"
DEFAULT_ERROR_OBSERVABILITY_ACK_STATE = Path(".cache") / "state" / "error_observability_ack.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _preview(value: Any, limit: int = 400) -> str:
    if isinstance(value, list):
        text = "\n".join(str(item) for item in value if isinstance(item, (str, int, float, bool)))
    else:
        text = str(value or "")
    text = text.replace("\r", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _item_signature(item: dict[str, Any]) -> str:
    payload = {
        "source_type": str(item.get("source_type") or ""),
        "source_name": str(item.get("source_name") or ""),
        "component": str(item.get("component") or ""),
        "occurred_at": str(item.get("occurred_at") or ""),
        "message": str(item.get("message") or ""),
        "report_path": str(item.get("report_path") or ""),
        "return_code": int(item.get("return_code") or 0),
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _default_ack_state() -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": "",
        "workspace_root": "",
        "ack_entries": [],
    }


def load_error_observability_ack_state(*, workspace_root: Path) -> tuple[dict[str, Any], str]:
    path = workspace_root / DEFAULT_ERROR_OBSERVABILITY_ACK_STATE
    if not path.exists():
        return _default_ack_state(), ""
    try:
        raw = _load_json(path)
    except Exception:
        return _default_ack_state(), _rel_path(workspace_root, path)
    if not isinstance(raw, dict):
        return _default_ack_state(), _rel_path(workspace_root, path)
    entries_raw = raw.get("ack_entries") if isinstance(raw.get("ack_entries"), list) else []
    entries = []
    for item in entries_raw:
        if not isinstance(item, dict):
            continue
        sig = str(item.get("signature") or "").strip()
        if not sig:
            continue
        entries.append(
            {
                "signature": sig,
                "source_type": str(item.get("source_type") or ""),
                "component": str(item.get("component") or ""),
                "occurred_at": str(item.get("occurred_at") or ""),
                "message": str(item.get("message") or ""),
                "acked_at": str(item.get("acked_at") or ""),
            }
        )
    return (
        {
            "version": "v1",
            "generated_at": str(raw.get("generated_at") or ""),
            "workspace_root": str(raw.get("workspace_root") or workspace_root),
            "ack_entries": entries,
        },
        _rel_path(workspace_root, path),
    )


def write_error_observability_ack_state(*, workspace_root: Path, state: dict[str, Any]) -> str:
    path = workspace_root / DEFAULT_ERROR_OBSERVABILITY_ACK_STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "ack_entries": [entry for entry in state.get("ack_entries", []) if isinstance(entry, dict)],
    }
    path.write_text(_dump_json(payload), encoding="utf-8")
    return _rel_path(workspace_root, path)


def _annotate_ack_state(
    *,
    workspace_root: Path,
    report: dict[str, Any],
    ack_state: dict[str, Any],
    ack_state_path: str,
) -> dict[str, Any]:
    ack_entries = ack_state.get("ack_entries") if isinstance(ack_state.get("ack_entries"), list) else []
    acked_by_sig = {
        str(entry.get("signature") or ""): entry for entry in ack_entries if isinstance(entry, dict) and entry.get("signature")
    }
    items_in = report.get("items") if isinstance(report.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for raw in items_in:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        signature = _item_signature(item)
        item["signature"] = signature
        acked_entry = acked_by_sig.get(signature)
        if isinstance(acked_entry, dict):
            item["ack_state"] = "ACKED"
            item["acked_at"] = str(acked_entry.get("acked_at") or "")
        else:
            item["ack_state"] = "ACTIVE"
        items.append(item)

    active_items = [item for item in items if str(item.get("ack_state") or "") != "ACKED"]
    latest_active = active_items[0] if active_items else {}
    scanned_sources = any(
        [
            (workspace_root / ".cache" / "reports" / "module_delivery_lanes").exists(),
            (workspace_root / "evidence").exists(),
            (workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json").exists(),
            (workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl").exists(),
        ]
    )
    notes = [str(item) for item in report.get("notes", []) if isinstance(item, str)]
    if items and not active_items:
        notes.append("all_items_acked")

    build_active = len([item for item in active_items if str(item.get("source_type") or "") == "build"])
    runner_active = len([item for item in active_items if str(item.get("source_type") or "") == "runner"])
    browser_active = len([item for item in active_items if str(item.get("source_type") or "") == "browser"])
    acked_items_total = len(items) - len(active_items)

    updated = dict(report)
    updated["status"] = "WARN" if active_items else ("OK" if scanned_sources else "IDLE")
    updated["ack_state_path"] = ack_state_path
    updated["ack_entries_total"] = len(acked_by_sig)
    updated["acked_items_total"] = acked_items_total
    updated["active_items_total"] = len(active_items)
    updated["active_build_count"] = build_active
    updated["active_runner_count"] = runner_active
    updated["active_browser_count"] = browser_active
    updated["latest_source_type"] = str(latest_active.get("source_type") or "")
    updated["latest_source_name"] = str(latest_active.get("source_name") or "")
    updated["latest_occurred_at"] = str(latest_active.get("occurred_at") or "")
    updated["latest_message"] = str(latest_active.get("message") or "")
    updated["latest_report_path"] = str(latest_active.get("report_path") or "")
    updated["notes"] = sorted(set(notes))
    updated["items"] = items
    return updated


def _collect_module_delivery_items(*, workspace_root: Path, max_items: int) -> tuple[list[dict[str, Any]], list[str]]:
    lane_dir = workspace_root / ".cache" / "reports" / "module_delivery_lanes"
    if not lane_dir.exists():
        return [], []

    items: list[dict[str, Any]] = []
    notes: list[str] = []
    for path in sorted(lane_dir.glob("*.v1.json")):
        try:
            report = _load_json(path)
        except Exception:
            items.append(
                {
                    "source_type": "build",
                    "source_name": "module_delivery_lane",
                    "component": path.stem,
                    "status": "WARN",
                    "occurred_at": "",
                    "message": "invalid lane report",
                    "report_path": _rel_path(workspace_root, path),
                }
            )
            notes.append(f"module_delivery_invalid:{path.name}")
            continue
        if not isinstance(report, dict):
            continue

        status = str(report.get("status") or "").upper() or "WARN"
        timed_out = bool(report.get("timed_out", False))
        return_code = _safe_int(report.get("return_code"))
        if status == "OK" and not timed_out and return_code == 0:
            continue
        lane = str(report.get("lane") or path.stem)
        stderr_preview = _preview(report.get("stderr_tail"))
        stdout_preview = _preview(report.get("stdout_tail"))
        message = stderr_preview or stdout_preview or f"lane={lane} rc={return_code}"
        item: dict[str, Any] = {
            "source_type": "build",
            "source_name": "module_delivery_lane",
            "component": lane,
            "status": "WARN" if timed_out and status == "OK" else status,
            "occurred_at": str(report.get("finished_at") or report.get("started_at") or ""),
            "message": message,
            "report_path": _rel_path(workspace_root, path),
            "return_code": return_code,
        }
        if stdout_preview:
            item["stdout_preview"] = stdout_preview
        if stderr_preview:
            item["stderr_preview"] = stderr_preview
        items.append(item)

    items.sort(key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("component") or "")), reverse=True)
    return items[:max_items], notes


def _collect_runner_items(*, workspace_root: Path, max_items: int) -> tuple[list[dict[str, Any]], list[str]]:
    evidence_root = workspace_root / "evidence"
    if not evidence_root.exists():
        return [], []

    candidates = list(evidence_root.rglob("summary.json"))
    candidates.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)

    items: list[dict[str, Any]] = []
    notes: list[str] = []
    for path in candidates[:200]:
        try:
            summary = _load_json(path)
        except Exception:
            notes.append(f"runner_summary_invalid:{path.name}")
            continue
        if not isinstance(summary, dict):
            continue

        status = str(summary.get("status") or summary.get("result_state") or "").upper()
        if status not in {"FAILED", "FAIL"} and not summary.get("error") and not summary.get("resume_error"):
            continue

        message = _preview(
            summary.get("policy_violation_code")
            or summary.get("error_code")
            or summary.get("resume_error")
            or summary.get("error")
        )
        item: dict[str, Any] = {
            "source_type": "runner",
            "source_name": "orchestrator_summary",
            "component": str(summary.get("workflow_id") or summary.get("run_id") or path.parent.name),
            "status": "FAIL",
            "occurred_at": str(summary.get("finished_at") or summary.get("resumed_at") or summary.get("started_at") or ""),
            "message": message or "runner failure",
            "report_path": _rel_path(workspace_root, path),
        }
        if isinstance(summary.get("failed_return_code"), int):
            item["return_code"] = int(summary.get("failed_return_code"))
        if isinstance(summary.get("failed_stdout_preview"), str) and summary.get("failed_stdout_preview"):
            item["stdout_preview"] = _preview(summary.get("failed_stdout_preview"))
        if isinstance(summary.get("failed_stderr_preview"), str) and summary.get("failed_stderr_preview"):
            item["stderr_preview"] = _preview(summary.get("failed_stderr_preview"))
        items.append(item)

    items.sort(key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("component") or "")), reverse=True)
    return items[:max_items], notes


def _collect_browser_items(*, workspace_root: Path, max_items: int) -> tuple[list[dict[str, Any]], list[str]]:
    summary_path = workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json"
    events_path = workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl"
    if not summary_path.exists() and not events_path.exists():
        return [], []

    items: list[dict[str, Any]] = []
    notes: list[str] = []
    if events_path.exists():
        try:
            rows = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            rows = []
            notes.append("browser_events_invalid")
        for raw in rows[-max_items:]:
            try:
                event = json.loads(raw)
            except Exception:
                notes.append("browser_event_row_invalid")
                continue
            if not isinstance(event, dict):
                continue
            item: dict[str, Any] = {
                "source_type": "browser",
                "source_name": "cockpit_frontend",
                "component": str(event.get("event_type") or "frontend"),
                "status": "WARN",
                "occurred_at": str(event.get("ts") or ""),
                "message": _preview(event.get("message") or "frontend error"),
                "report_path": _rel_path(workspace_root, events_path),
            }
            stack = _preview(event.get("stack"), limit=600)
            if stack:
                item["stderr_preview"] = stack
            items.append(item)
    elif summary_path.exists():
        try:
            summary = _load_json(summary_path)
        except Exception:
            summary = {}
            notes.append("browser_summary_invalid")
        if isinstance(summary, dict) and int(summary.get("total_events") or 0) > 0:
            items.append(
                {
                    "source_type": "browser",
                    "source_name": "cockpit_frontend",
                    "component": str(summary.get("last_event_type") or "frontend"),
                    "status": "WARN",
                    "occurred_at": str(summary.get("last_event_at") or ""),
                    "message": _preview(summary.get("last_message") or "frontend error"),
                    "report_path": _rel_path(workspace_root, summary_path),
                }
            )

    items.sort(key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("component") or "")), reverse=True)
    return items[:max_items], notes


def build_error_observability_report(*, workspace_root: Path, max_items: int = 25) -> dict[str, Any]:
    build_items, build_notes = _collect_module_delivery_items(workspace_root=workspace_root, max_items=max_items)
    runner_items, runner_notes = _collect_runner_items(workspace_root=workspace_root, max_items=max_items)
    browser_items, browser_notes = _collect_browser_items(workspace_root=workspace_root, max_items=max_items)

    items = (build_items + runner_items + browser_items)[:]
    items.sort(
        key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("source_type") or ""), str(item.get("component") or "")),
        reverse=True,
    )
    items = items[:max_items]

    items_total = len(items)
    build_count = len([item for item in items if str(item.get("source_type") or "") == "build"])
    runner_count = len([item for item in items if str(item.get("source_type") or "") == "runner"])
    browser_count = len([item for item in items if str(item.get("source_type") or "") == "browser"])

    scanned_sources = any(
        [
            (workspace_root / ".cache" / "reports" / "module_delivery_lanes").exists(),
            (workspace_root / "evidence").exists(),
            (workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json").exists(),
            (workspace_root / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl").exists(),
        ]
    )
    base_report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": "WARN" if items_total > 0 else ("OK" if scanned_sources else "IDLE"),
        "items_total": items_total,
        "build_count": build_count,
        "runner_count": runner_count,
        "browser_count": browser_count,
        "ack_state_path": "",
        "ack_entries_total": 0,
        "acked_items_total": 0,
        "active_items_total": items_total,
        "active_build_count": build_count,
        "active_runner_count": runner_count,
        "active_browser_count": browser_count,
        "latest_source_type": str(items[0].get("source_type") or "") if items else "",
        "latest_source_name": str(items[0].get("source_name") or "") if items else "",
        "latest_occurred_at": str(items[0].get("occurred_at") or "") if items else "",
        "latest_message": str(items[0].get("message") or "") if items else "",
        "latest_report_path": str(items[0].get("report_path") or "") if items else "",
        "sources": {
            "module_delivery_report_dir": ".cache/reports/module_delivery_lanes",
            "runner_evidence_root": "evidence",
            "browser_events_path": ".cache/reports/cockpit_frontend_telemetry.v1.jsonl",
            "browser_summary_path": ".cache/reports/cockpit_frontend_telemetry_summary.v1.json",
        },
        "notes": sorted(set(build_notes + runner_notes + browser_notes)),
        "items": items,
    }
    ack_state, ack_state_path = load_error_observability_ack_state(workspace_root=workspace_root)
    return _annotate_ack_state(
        workspace_root=workspace_root,
        report=base_report,
        ack_state=ack_state,
        ack_state_path=ack_state_path,
    )


def project_error_observability_section(report: dict[str, Any], *, report_path: str = "") -> dict[str, Any]:
    return {
        "status": str(report.get("status") or "IDLE"),
        "report_path": report_path,
        "items_total": int(report.get("items_total") or 0),
        "active_items_total": int(report.get("active_items_total") or 0),
        "acked_items_total": int(report.get("acked_items_total") or 0),
        "build_count": int(report.get("build_count") or 0),
        "runner_count": int(report.get("runner_count") or 0),
        "browser_count": int(report.get("browser_count") or 0),
        "active_build_count": int(report.get("active_build_count") or 0),
        "active_runner_count": int(report.get("active_runner_count") or 0),
        "active_browser_count": int(report.get("active_browser_count") or 0),
        "ack_state_path": str(report.get("ack_state_path") or ""),
        "latest_source_type": str(report.get("latest_source_type") or ""),
        "latest_source_name": str(report.get("latest_source_name") or ""),
        "latest_occurred_at": str(report.get("latest_occurred_at") or ""),
        "latest_message": str(report.get("latest_message") or ""),
        "latest_report_path": str(report.get("latest_report_path") or ""),
        "notes": [str(item) for item in report.get("notes", []) if isinstance(item, str)],
    }


def write_error_observability_report(
    *,
    workspace_root: Path,
    report: dict[str, Any],
    out_path: Path | None = None,
) -> str:
    resolved = out_path or (workspace_root / DEFAULT_ERROR_OBSERVABILITY_REPORT)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(_dump_json(report), encoding="utf-8")
    return _rel_path(workspace_root, resolved)


def run_error_observability(*, workspace_root: Path, out: str | None = None) -> dict[str, Any]:
    report = build_error_observability_report(workspace_root=workspace_root)
    out_path = None
    if out:
        out_path = Path(out)
        if not out_path.is_absolute():
            out_path = workspace_root / out_path
    report_path = write_error_observability_report(workspace_root=workspace_root, report=report, out_path=out_path)
    payload = dict(report)
    payload["report_path"] = report_path
    return payload


def run_error_observability_ack(*, workspace_root: Path, mode: str) -> dict[str, Any]:
    normalized_mode = str(mode or "").strip().lower()
    ack_state, ack_state_path = load_error_observability_ack_state(workspace_root=workspace_root)
    if normalized_mode == "show":
        return {
            "status": "OK",
            "mode": "show",
            "ack_state_path": ack_state_path or DEFAULT_ERROR_OBSERVABILITY_ACK_STATE.as_posix(),
            "ack_entries_total": len(ack_state.get("ack_entries", [])),
            "ack_state": ack_state,
        }
    if normalized_mode == "clear":
        cleared = _default_ack_state()
        path = write_error_observability_ack_state(workspace_root=workspace_root, state=cleared)
        updated = run_error_observability(workspace_root=workspace_root)
        return {
            "status": "OK",
            "mode": "clear",
            "ack_state_path": path,
            "cleared": True,
            "ack_entries_total": 0,
            "active_items_after": int(updated.get("active_items_total") or 0),
            "report_path": str(updated.get("report_path") or DEFAULT_ERROR_OBSERVABILITY_REPORT.as_posix()),
        }
    if normalized_mode != "ack-current":
        return {"status": "FAIL", "error_code": "INVALID_MODE", "mode": normalized_mode}

    report = build_error_observability_report(workspace_root=workspace_root)
    items = report.get("items") if isinstance(report.get("items"), list) else []
    active_items = [
        item for item in items if isinstance(item, dict) and str(item.get("ack_state") or "") == "ACTIVE"
    ]
    current_entries = ack_state.get("ack_entries") if isinstance(ack_state.get("ack_entries"), list) else []
    entries_by_sig = {
        str(entry.get("signature") or ""): dict(entry)
        for entry in current_entries
        if isinstance(entry, dict) and entry.get("signature")
    }
    added = 0
    acked_at = _now_iso()
    for item in active_items:
        signature = str(item.get("signature") or "").strip()
        if not signature or signature in entries_by_sig:
            continue
        entries_by_sig[signature] = {
            "signature": signature,
            "source_type": str(item.get("source_type") or ""),
            "component": str(item.get("component") or ""),
            "occurred_at": str(item.get("occurred_at") or ""),
            "message": str(item.get("message") or ""),
            "acked_at": acked_at,
        }
        added += 1
    next_state = {
        "version": "v1",
        "generated_at": acked_at,
        "workspace_root": str(workspace_root),
        "ack_entries": sorted(entries_by_sig.values(), key=lambda entry: str(entry.get("acked_at") or ""), reverse=True),
    }
    path = write_error_observability_ack_state(workspace_root=workspace_root, state=next_state)
    updated = run_error_observability(workspace_root=workspace_root)
    return {
        "status": "OK",
        "mode": "ack-current",
        "ack_state_path": path,
        "added": added,
        "active_items_before": len(active_items),
        "active_items_after": int(updated.get("active_items_total") or 0),
        "ack_entries_total": len(next_state.get("ack_entries", [])),
        "report_path": str(updated.get("report_path") or DEFAULT_ERROR_OBSERVABILITY_REPORT.as_posix()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.error_observability_report", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", default=str(DEFAULT_ERROR_OBSERVABILITY_REPORT))
    ap.add_argument("--ack-mode", default="")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    if str(args.ack_mode or "").strip():
        payload = run_error_observability_ack(workspace_root=workspace_root, mode=str(args.ack_mode or ""))
    else:
        payload = run_error_observability(workspace_root=workspace_root, out=str(args.out or ""))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") in {"OK", "WARN", "IDLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
