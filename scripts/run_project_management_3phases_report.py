#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SEVERITY_ORDER = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1, "UNKNOWN": 0}
_SMOKE_CODES = {
    "NONE",
    "SCRIPT_BUDGET",
    "READONLY_CMD_NOT_ALLOWED",
    "READONLY_MODE_VIOLATION",
    "CORE_IMMUTABLE_WRITE_BLOCKED",
    "WORKSPACE_ROOT_VIOLATION",
    "SANITIZE_VIOLATION",
    "CONTENT_MISMATCH",
    "CMD_FAILED",
    "SMOKE_ASSERTION_FAILED",
    "UNKNOWN",
}
_SMOKE_CODE_TO_CATEGORY = {
    "NONE": "NONE",
    "SCRIPT_BUDGET": "MAINTAINABILITY",
    "READONLY_CMD_NOT_ALLOWED": "SAFETY_GUARDRAIL",
    "READONLY_MODE_VIOLATION": "SAFETY_GUARDRAIL",
    "CORE_IMMUTABLE_WRITE_BLOCKED": "CORE_LOCK",
    "WORKSPACE_ROOT_VIOLATION": "BOUNDARY",
    "SANITIZE_VIOLATION": "SECURITY",
    "CONTENT_MISMATCH": "IDEMPOTENCY",
    "CMD_FAILED": "ROADMAP_GATE",
    "SMOKE_ASSERTION_FAILED": "SMOKE_ASSERTION",
    "UNKNOWN": "UNKNOWN",
}
_SMOKE_CODE_TO_SEVERITY = {
    "NONE": "INFO",
    "SCRIPT_BUDGET": "HIGH",
    "READONLY_CMD_NOT_ALLOWED": "HIGH",
    "READONLY_MODE_VIOLATION": "HIGH",
    "CORE_IMMUTABLE_WRITE_BLOCKED": "CRITICAL",
    "WORKSPACE_ROOT_VIOLATION": "HIGH",
    "SANITIZE_VIOLATION": "CRITICAL",
    "CONTENT_MISMATCH": "MEDIUM",
    "CMD_FAILED": "HIGH",
    "SMOKE_ASSERTION_FAILED": "HIGH",
    "UNKNOWN": "UNKNOWN",
}
_SMOKE_SEVERITY_ORDER = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1, "UNKNOWN": 0}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_text(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.loads(handle.read())


def _build_extension_issue_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    critical_items: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        repo_slug = str(entry.get("repo_slug") or "")
        repo_root = str(entry.get("repo_root") or "")
        workspace_root = str(entry.get("workspace_root") or "")
        for issue in entry.get("command_issues", []) if isinstance(entry.get("command_issues"), list) else []:
            command = str(issue.get("command", "")).strip()
            status = str(issue.get("status", "")).strip().upper()
            if not command or not status:
                continue
            if status not in {"WARN", "FAIL", "ERROR", "BLOCKED"}:
                continue
            critical_items.append(
                {
                    "repo_slug": repo_slug,
                    "repo_root": repo_root,
                    "workspace_root": workspace_root,
                    "command": command,
                    "status": status,
                }
            )

    by_command: dict[str, dict[str, int]] = {}
    for issue in critical_items:
        entry = by_command.setdefault(issue["command"], {"WARN": 0, "FAIL": 0, "ERROR": 0, "BLOCKED": 0})
        entry[issue["status"]] = entry.get(issue["status"], 0) + 1

    repo_count = len(set(item["repo_slug"] for item in critical_items if item["repo_slug"])) if critical_items else 0
    return {
        "items": critical_items,
        "totals": {
            "warn": sum(1 for item in critical_items if item["status"] == "WARN"),
            "fail": sum(1 for item in critical_items if item["status"] in {"FAIL", "ERROR", "BLOCKED"}),
            "repo_count": repo_count,
        },
        "by_command": by_command,
    }


def _build_blocking_reasons(entries: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        repo_slug = str(entry.get("repo_slug") or "")
        repo_root = str(entry.get("repo_root") or "")
        workspace_root = str(entry.get("workspace_root") or "")
        for issue in entry.get("command_issues", []) if isinstance(entry.get("command_issues"), list) else []:
            if not isinstance(issue, dict):
                continue
            status = str(issue.get("status") or "").strip().upper()
            if status not in {"WARN", "FAIL", "ERROR", "BLOCKED"}:
                continue
            blocker_code = str(issue.get("blocker_code") or "").strip().upper()
            blocker_category = str(issue.get("blocker_category") or "").strip().upper()
            blocker_severity = str(issue.get("blocker_severity") or "").strip().upper()
            if not blocker_code:
                blocker_code = "COMMAND_WARN" if status == "WARN" else "COMMAND_FAIL"
            if not blocker_category:
                blocker_category = "GENERAL"
            if blocker_severity not in _SEVERITY_ORDER:
                blocker_severity = "LOW" if status == "WARN" else "HIGH"

            items.append(
                {
                    "repo_slug": repo_slug,
                    "repo_root": repo_root,
                    "workspace_root": workspace_root,
                    "command": str(issue.get("command") or "").strip(),
                    "status": status,
                    "return_code": str(issue.get("return_code") or "").strip(),
                    "error_code": str(issue.get("error_code") or "").strip(),
                    "blocker_code": blocker_code,
                    "blocker_category": blocker_category,
                    "blocker_severity": blocker_severity,
                    "source": str(issue.get("source") or "").strip(),
                }
            )

    by_code: dict[str, int] = {}
    by_command: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    grouped: dict[str, dict[str, Any]] = {}

    for item in items:
        code = item["blocker_code"]
        command = item["command"] or "unknown"
        sev = item["blocker_severity"]
        cat = item["blocker_category"]
        by_code[code] = by_code.get(code, 0) + 1
        by_command[command] = by_command.get(command, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1

        rec = grouped.setdefault(
            code,
            {
                "blocker_code": code,
                "count": 0,
                "severity": sev,
                "category": cat,
                "commands": set(),
                "repos": set(),
            },
        )
        rec["count"] = int(rec.get("count", 0)) + 1
        if _SEVERITY_ORDER.get(sev, 0) > _SEVERITY_ORDER.get(str(rec.get("severity") or "").upper(), 0):
            rec["severity"] = sev
        rec["commands"].add(command)
        if item["repo_slug"]:
            rec["repos"].add(item["repo_slug"])

    top_blockers: list[dict[str, Any]] = []
    for rec in grouped.values():
        top_blockers.append(
            {
                "blocker_code": str(rec.get("blocker_code") or ""),
                "count": int(rec.get("count") or 0),
                "severity": str(rec.get("severity") or ""),
                "category": str(rec.get("category") or ""),
                "commands": sorted(list(rec.get("commands") or [])),
                "repos": sorted(list(rec.get("repos") or [])),
            }
        )

    top_blockers.sort(
        key=lambda r: (
            -_SEVERITY_ORDER.get(str(r.get("severity") or "").upper(), -1),
            -int(r.get("count") or 0),
            str(r.get("blocker_code") or ""),
        )
    )

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "total_items": len(items),
        "by_blocker_code": dict(sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_command": dict(sorted(by_command.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_severity": dict(
            sorted(by_severity.items(), key=lambda kv: (-kv[1], -_SEVERITY_ORDER.get(str(kv[0]).upper(), -1), kv[0]))
        ),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
        "top_blockers": top_blockers[:20],
        "items": items,
    }


def _normalize_smoke_root_error_code(*, status: str, code: str) -> str:
    raw = str(code or "").strip().upper()
    if raw in _SMOKE_CODES:
        return raw
    if str(status or "").strip().upper() == "OK":
        return "NONE"
    return "UNKNOWN"


def _normalize_smoke_category(*, raw: str, code: str) -> str:
    value = str(raw or "").strip().upper()
    if value:
        return value
    return _SMOKE_CODE_TO_CATEGORY.get(code, "UNKNOWN")


def _normalize_smoke_severity(*, raw: str, code: str) -> str:
    value = str(raw or "").strip().upper()
    if value in _SMOKE_SEVERITY_ORDER:
        return value
    return _SMOKE_CODE_TO_SEVERITY.get(code, "UNKNOWN")


def _count_sorted(data: dict[str, int], *, severity: bool = False) -> dict[str, int]:
    if not data:
        return {}

    if severity:
        keys = sorted(
            data.keys(),
            key=lambda k: (-data.get(k, 0), -_SMOKE_SEVERITY_ORDER.get(str(k).upper(), -1), str(k)),
        )
    else:
        keys = sorted(data.keys(), key=lambda k: (-data.get(k, 0), str(k)))
    return {k: int(data[k]) for k in keys}


def _load_smoke_root_cause_payload(repo_root: Path, report_path: str) -> dict[str, Any]:
    raw = str(report_path or "").strip()
    if not raw:
        return {}
    path = Path(raw)
    abs_path = path if path.is_absolute() else (repo_root / path).resolve()
    if not abs_path.exists() or not abs_path.is_file():
        return {}
    try:
        loaded = _load_json_text(abs_path)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _compact_step_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    keep_keys = {
        "status",
        "error_code",
        "root_cause_report",
        "root_error_code",
        "root_error_category",
        "root_error_severity",
        "classification_source",
        "failed_step_id",
        "failed_cmd",
        "report",
        "report_path",
        "out",
        "evidence_path",
        "deprecation_warning_count",
        "deprecation_gate_exceeded",
    }
    out = {k: payload.get(k) for k in payload.keys() if k in keep_keys}
    return out if isinstance(out, dict) else {}


def _build_smoke_root_cause_aggregation(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    repo_items: list[dict[str, Any]] = []
    missing_smoke_step_repos: list[str] = []
    failed_items: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        repo_slug = str(entry.get("repo_slug") or "")
        repo_id = str(entry.get("repo_id") or "")
        repo_root = Path(str(entry.get("repo_root") or "")).expanduser()
        workspace_root = str(entry.get("workspace_root") or "")
        steps = entry.get("steps")
        smoke_step = None
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if str(step.get("command") or "").strip() == "smoke":
                    smoke_step = step
                    break
        if not isinstance(smoke_step, dict):
            if repo_slug:
                missing_smoke_step_repos.append(repo_slug)
            continue

        step_status = str(smoke_step.get("status") or "").strip().upper()
        payload = smoke_step.get("payload") if isinstance(smoke_step.get("payload"), dict) else {}

        report_path = str(payload.get("root_cause_report") or "").strip()
        if not report_path:
            ev_paths = smoke_step.get("evidence_paths")
            if isinstance(ev_paths, list):
                for item in ev_paths:
                    if not isinstance(item, str):
                        continue
                    if "smoke_root_cause_report.v1.json" in item:
                        report_path = item.strip()
                        break
        report_payload = _load_smoke_root_cause_payload(repo_root=repo_root, report_path=report_path)

        root_error_code = _normalize_smoke_root_error_code(
            status=step_status,
            code=str(payload.get("root_error_code") or report_payload.get("root_error_code") or ""),
        )
        root_error_category = _normalize_smoke_category(
            raw=str(payload.get("root_error_category") or report_payload.get("root_error_category") or ""),
            code=root_error_code,
        )
        root_error_severity = _normalize_smoke_severity(
            raw=str(payload.get("root_error_severity") or report_payload.get("root_error_severity") or ""),
            code=root_error_code,
        )

        record = {
            "repo_slug": repo_slug,
            "repo_id": repo_id,
            "repo_root": str(repo_root),
            "workspace_root": workspace_root,
            "status": step_status or "UNKNOWN",
            "root_error_code": root_error_code,
            "root_error_category": root_error_category,
            "root_error_severity": root_error_severity,
            "classification_source": str(
                payload.get("classification_source") or report_payload.get("classification_source") or ""
            )
            or None,
            "root_cause_report": report_path or None,
            "failed_step_id": str(payload.get("failed_step_id") or report_payload.get("failed_step_id") or "") or None,
            "failed_cmd": str(payload.get("failed_cmd") or report_payload.get("failed_cmd") or "") or None,
        }
        repo_items.append(record)

        by_code[root_error_code] = by_code.get(root_error_code, 0) + 1
        by_category[root_error_category] = by_category.get(root_error_category, 0) + 1
        by_severity[root_error_severity] = by_severity.get(root_error_severity, 0) + 1

        if record["status"] in {"FAIL", "ERROR", "BLOCKED"}:
            failed_items.append(record)

    failed_items_sorted = sorted(
        failed_items,
        key=lambda item: (
            -_SMOKE_SEVERITY_ORDER.get(str(item.get("root_error_severity") or "").upper(), -1),
            str(item.get("repo_slug") or ""),
        ),
    )
    repos_non_none_root_cause = sum(1 for item in repo_items if str(item.get("root_error_code")) != "NONE")
    repos_failed_smoke = sum(1 for item in repo_items if str(item.get("status")) in {"FAIL", "ERROR", "BLOCKED"})

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "repos_total": len([entry for entry in entries if isinstance(entry, dict)]),
        "repos_with_smoke_step": len(repo_items),
        "repos_missing_smoke_step": len(missing_smoke_step_repos),
        "repos_failed_smoke": repos_failed_smoke,
        "repos_non_none_root_cause": repos_non_none_root_cause,
        "by_root_error_code": _count_sorted(by_code),
        "by_root_error_category": _count_sorted(by_category),
        "by_root_error_severity": _count_sorted(by_severity, severity=True),
        "top_failed_repos": failed_items_sorted[:20],
        "missing_smoke_step_repos": sorted(missing_smoke_step_repos),
        "repos": repo_items,
    }

