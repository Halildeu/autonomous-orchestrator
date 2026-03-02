from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SMOKE_ROOT_CAUSE_TAXONOMY_VERSION = "v1"
DEFAULT_SMOKE_ROOT_CAUSE_REPORT = ".cache/reports/smoke_root_cause_report.v1.json"

SMOKE_ROOT_CAUSE_TAXONOMY: dict[str, dict[str, Any]] = {
    "NONE": {
        "category": "NONE",
        "severity": "INFO",
        "retryable": False,
        "summary": "Smoke run passed; no root cause.",
        "ci_action": "No action required.",
    },
    "SCRIPT_BUDGET": {
        "category": "MAINTAINABILITY",
        "severity": "HIGH",
        "retryable": False,
        "summary": "Script Budget gate violated (hard/no-growth).",
        "ci_action": "Split oversized scripts or update baseline via approved CHG.",
    },
    "READONLY_CMD_NOT_ALLOWED": {
        "category": "SAFETY_GUARDRAIL",
        "severity": "HIGH",
        "retryable": False,
        "summary": "Readonly dry-run attempted a non-allowlisted command.",
        "ci_action": "Use allowlisted readonly gates only; move mutating command to apply path.",
    },
    "READONLY_MODE_VIOLATION": {
        "category": "SAFETY_GUARDRAIL",
        "severity": "HIGH",
        "retryable": False,
        "summary": "Readonly mode detected filesystem or git side-effect.",
        "ci_action": "Remove side-effects from readonly flows and re-run smoke.",
    },
    "CORE_IMMUTABLE_WRITE_BLOCKED": {
        "category": "CORE_LOCK",
        "severity": "CRITICAL",
        "retryable": False,
        "summary": "Core immutability blocked a write outside allowed unlock scope.",
        "ci_action": "Keep writes workspace-scoped or provide controlled CORE_UNLOCK evidence path.",
    },
    "WORKSPACE_ROOT_VIOLATION": {
        "category": "BOUNDARY",
        "severity": "HIGH",
        "retryable": False,
        "summary": "Operation attempted outside workspace root boundary.",
        "ci_action": "Normalize paths into workspace root and keep fail-closed path guards.",
    },
    "SANITIZE_VIOLATION": {
        "category": "SECURITY",
        "severity": "CRITICAL",
        "retryable": False,
        "summary": "Sanitize scan detected forbidden secret/pattern.",
        "ci_action": "Remove sensitive content and re-run sanitize and smoke.",
    },
    "CONTENT_MISMATCH": {
        "category": "IDEMPOTENCY",
        "severity": "MEDIUM",
        "retryable": False,
        "summary": "Idempotent write check failed due to content mismatch.",
        "ci_action": "Align expected content or switch to explicit update step.",
    },
    "CMD_FAILED": {
        "category": "ROADMAP_GATE",
        "severity": "HIGH",
        "retryable": True,
        "summary": "Roadmap gate command returned non-zero exit code.",
        "ci_action": "Inspect failed gate command stderr/stdout and fix underlying command failure.",
    },
    "SMOKE_ASSERTION_FAILED": {
        "category": "SMOKE_ASSERTION",
        "severity": "HIGH",
        "retryable": True,
        "summary": "Smoke assertion failed but no explicit roadmap root-cause line was emitted.",
        "ci_action": "Inspect smoke output and add/repair deterministic failure classification.",
    },
    "UNKNOWN": {
        "category": "UNKNOWN",
        "severity": "MEDIUM",
        "retryable": True,
        "summary": "Root cause could not be classified into known taxonomy.",
        "ci_action": "Inspect logs and extend SMOKE_ROOT_CAUSE taxonomy mapping.",
    },
}

_ROOT_CAUSE_LINE_RE = re.compile(
    r"SMOKE_ROOT_CAUSE\s+root_error_code=(\S+)\s+failed_step_id=(\S+)\s+failed_cmd=(.+)"
)
_ROOT_STDERR_LINE_RE = re.compile(r"SMOKE_ROOT_STDERR\s+(.+)")

_TOKEN_TO_CODE: tuple[tuple[str, str], ...] = (
    ("check_script_budget.py", "SCRIPT_BUDGET"),
    ("PY_FILE_NO_GROWTH", "SCRIPT_BUDGET"),
    ("PY_FILE_GROWTH_FORBIDDEN", "SCRIPT_BUDGET"),
    ("READONLY_CMD_NOT_ALLOWED", "READONLY_CMD_NOT_ALLOWED"),
    ("READONLY_MODE_VIOLATION", "READONLY_MODE_VIOLATION"),
    ("CORE_IMMUTABLE_WRITE_BLOCKED", "CORE_IMMUTABLE_WRITE_BLOCKED"),
    ("WORKSPACE_ROOT_VIOLATION", "WORKSPACE_ROOT_VIOLATION"),
    ("SANITIZE_VIOLATION", "SANITIZE_VIOLATION"),
    ("CONTENT_MISMATCH", "CONTENT_MISMATCH"),
)


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def taxonomy_entry_for_code(code: str) -> dict[str, Any]:
    normalized = normalize_root_error_code(code) or "UNKNOWN"
    base = SMOKE_ROOT_CAUSE_TAXONOMY.get(normalized) or SMOKE_ROOT_CAUSE_TAXONOMY["UNKNOWN"]
    return {
        "code": normalized,
        "category": str(base.get("category") or "UNKNOWN"),
        "severity": str(base.get("severity") or "MEDIUM"),
        "retryable": bool(base.get("retryable", True)),
        "summary": str(base.get("summary") or ""),
        "ci_action": str(base.get("ci_action") or ""),
    }


def normalize_root_error_code(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    code = raw.strip().upper()
    if not code:
        return ""
    return code if code in SMOKE_ROOT_CAUSE_TAXONOMY else "UNKNOWN"


def parse_smoke_root_cause_from_output(text: str) -> dict[str, str]:
    root_error_code = ""
    failed_step_id = ""
    failed_cmd = ""
    failed_stderr_preview = ""
    failed_error_code = ""

    for raw_line in reversed((text or "").splitlines()):
        line = raw_line.strip()
        if not failed_stderr_preview:
            m_stderr = _ROOT_STDERR_LINE_RE.search(line)
            if m_stderr:
                failed_stderr_preview = str(m_stderr.group(1) or "").strip()
        if root_error_code:
            continue
        m_root = _ROOT_CAUSE_LINE_RE.search(line)
        if not m_root:
            continue
        root_error_code = str(m_root.group(1) or "").strip()
        failed_step_id = str(m_root.group(2) or "").strip()
        failed_cmd = str(m_root.group(3) or "").strip()

    for obj in reversed(_extract_json_objects(text)):
        if not failed_error_code:
            raw = obj.get("failed_error_code")
            if isinstance(raw, str) and raw.strip():
                failed_error_code = raw.strip()
        if not failed_step_id:
            raw = obj.get("failed_step_id")
            if isinstance(raw, str) and raw.strip():
                failed_step_id = raw.strip()
        if not failed_cmd:
            raw = obj.get("failed_cmd")
            if isinstance(raw, str) and raw.strip():
                failed_cmd = raw.strip()
        if not failed_stderr_preview:
            raw = obj.get("failed_stderr_preview")
            if isinstance(raw, str) and raw.strip():
                failed_stderr_preview = raw.strip()
        if failed_error_code and failed_step_id and failed_cmd and failed_stderr_preview:
            break

    return {
        "root_error_code": root_error_code,
        "failed_step_id": failed_step_id,
        "failed_cmd": failed_cmd,
        "failed_stderr_preview": failed_stderr_preview,
        "failed_error_code": failed_error_code,
    }


def classify_smoke_root_cause(
    *,
    reported_root_error_code: str = "",
    failed_error_code: str = "",
    failed_cmd: str = "",
    text_blob: str = "",
) -> tuple[str, str]:
    reported = normalize_root_error_code(reported_root_error_code)
    failed = normalize_root_error_code(failed_error_code)
    cmd = str(failed_cmd or "").strip()
    blob = str(text_blob or "").strip()

    if reported and reported != "UNKNOWN":
        return (reported, "reported_root_error_code")

    if failed and failed != "UNKNOWN":
        if failed == "CMD_FAILED" and "check_script_budget.py" in cmd:
            return ("SCRIPT_BUDGET", "failed_error_code+cmd_hint")
        return (failed, "failed_error_code")

    haystack = "\n".join([cmd, blob, str(reported_root_error_code or ""), str(failed_error_code or "")]).lower()
    for token, code in _TOKEN_TO_CODE:
        if token.lower() in haystack:
            return (code, f"token:{token}")

    if "smoke test failed" in haystack:
        return ("SMOKE_ASSERTION_FAILED", "smoke_assertion_fallback")

    if reported == "UNKNOWN":
        return ("UNKNOWN", "reported_unknown")
    return ("UNKNOWN", "fallback")


def build_smoke_root_cause_report(
    *,
    status: str,
    level: str,
    reported_root_error_code: str = "",
    failed_error_code: str = "",
    failed_step_id: str = "",
    failed_cmd: str = "",
    failed_stderr_preview: str = "",
    combined_output: str = "",
) -> dict[str, Any]:
    normalized_status = str(status or "").strip().upper() or "FAIL"
    normalized_level = str(level or "").strip().lower() or "fast"

    if normalized_status == "OK":
        root_error_code = "NONE"
        source = "status_ok"
    else:
        root_error_code, source = classify_smoke_root_cause(
            reported_root_error_code=reported_root_error_code,
            failed_error_code=failed_error_code,
            failed_cmd=failed_cmd,
            text_blob="\n".join([failed_stderr_preview, combined_output]),
        )

    taxonomy = taxonomy_entry_for_code(root_error_code)
    return {
        "version": "v1",
        "taxonomy_version": SMOKE_ROOT_CAUSE_TAXONOMY_VERSION,
        "generated_at": _now_iso8601(),
        "status": normalized_status,
        "level": normalized_level,
        "root_error_code": taxonomy["code"],
        "root_error_category": taxonomy["category"],
        "root_error_severity": taxonomy["severity"],
        "root_error_retryable": taxonomy["retryable"],
        "root_error_summary": taxonomy["summary"],
        "root_error_ci_action": taxonomy["ci_action"],
        "classification_source": source,
        "failed_step_id": str(failed_step_id or "").strip() or None,
        "failed_cmd": str(failed_cmd or "").strip() or None,
        "failed_error_code": str(failed_error_code or "").strip() or None,
        "failed_stderr_preview": str(failed_stderr_preview or "").strip() or None,
    }


def write_smoke_root_cause_report(
    *,
    repo_root: Path,
    report: dict[str, Any],
    out_path: str = DEFAULT_SMOKE_ROOT_CAUSE_REPORT,
) -> str:
    target = Path(str(out_path or DEFAULT_SMOKE_ROOT_CAUSE_REPORT).strip() or DEFAULT_SMOKE_ROOT_CAUSE_REPORT)
    if not target.is_absolute():
        target = (repo_root / target).resolve()
    else:
        target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    root_resolved = repo_root.resolve()
    try:
        report_path = target.relative_to(root_resolved).as_posix()
    except Exception:
        report_path = str(target)

    payload = dict(report)
    payload["report_path"] = report_path
    target.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report_path
