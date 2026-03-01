#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from json import JSONDecoder, JSONDecodeError
from pathlib import Path
from typing import Any


RISK_CRITICAL_STATUSES = {"FAIL", "BLOCKED", "NOT_READY", "MISSING", "ERROR", "INVALID"}
RISK_HIGH_STATUSES = {"WARN", "IDLE", "UNKNOWN", "SKIPPED"}
CRITICAL_COMMANDS = {"policy-check", "script-budget", "smoke", "extension-registry", "extension-help", "doc-nav-check", "work-intake-check"}


@dataclass
class RepoContext:
    repo_root: Path
    workspace_root: Path
    repo_slug: str
    repo_id: str
    source: str
    notes: list[str] = field(default_factory=list)
    missing_workspace: bool = False
    force_critical: bool = False


def parse_bool(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]", "-", value.lower().strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug or "repo"


def _hash_tag(path: Path) -> str:
    return hashlib.sha1(path.as_posix().encode("utf-8")).hexdigest()[:8]


def _is_workspace_placeholder(path: Path) -> bool:
    value = str(path).strip()
    if not value:
        return True
    normalized = value.replace("\\", "/").rstrip("/")
    return normalized in {".", "./"}


def _load_json_text(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.loads(handle.read())


def _write_json_text(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _extract_json_payload(text: str) -> Any:
    if not text:
        return None
    line_payload = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            line_payload = parsed
    if isinstance(line_payload, dict):
        return line_payload

    decoder = JSONDecoder()
    for i in range(len(text)):
        if text[i] != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[i:])
        except JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _extract_status_from_text(text: str) -> str:
    for token in ["OK", "WARN", "IDLE", "FAIL", "BLOCKED", "ERROR", "MISSING", "INVALID", "NOT_READY", "SKIPPED", "QUEUED", "RUNNING"]:
        if f"status={token}" in text:
            return token
    return ""


def _collect_evidence(payload: Any, workspace_root: Path, fallback_root: Path | None = None) -> list[str]:
    if not isinstance(payload, dict):
        return []

    collected: list[str] = []
    seen: set[str] = set()
    queue: list[Any] = [payload]

    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key, value in item.items():
                lower_key = str(key or "").lower()
                if isinstance(value, (dict, list)):
                    queue.append(value)
                    continue
                if not isinstance(value, str):
                    continue
                if not lower_key.endswith("_path") and "path" not in lower_key:
                    continue
                text = value.strip()
                if not text:
                    continue
                if text not in seen:
                    seen.add(text)
                    collected.append(text)
                continue
        if isinstance(item, list):
            queue.extend(item)

    for item in list(payload.keys()) if isinstance(payload, dict) else []:
        if isinstance(item, str):
            val = payload.get(item)
            if isinstance(val, str) and val.endswith(".json") and val and val not in seen:
                seen.add(val)
                collected.append(val)

    evidence: list[str] = []
    for raw in collected:
        try:
            path = Path(raw)
            if path.is_absolute():
                candidate = path
            else:
                candidate = (workspace_root / raw).resolve()
                if fallback_root is not None and not candidate.exists():
                    alt = (fallback_root / raw).resolve()
                    if alt.exists():
                        candidate = alt
            evidence.append(str(candidate))
        except Exception:
            evidence.append(raw)

    return evidence


def _risk_level(score: int) -> str:
    if score >= 10:
        return "CRITICAL"
    if score >= 6:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def _risk_weight(raw_status: Any) -> int:
    status = str(raw_status or "").strip().upper()
    if status in RISK_CRITICAL_STATUSES:
        return 3
    if status in RISK_HIGH_STATUSES:
        return 1
    return 0


def _build_repo_status(workspace_root: Path) -> dict[str, Any]:
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    if not status_path.exists():
        return {
            "overall_status": "MISSING",
            "extensions_single_gate_status": "MISSING",
            "extensions_registry_status": "MISSING",
            "extensions_isolation_status": "MISSING",
            "quality_gate_status": "MISSING",
            "readiness_status": "MISSING",
            "status_path": str(status_path),
            "status_exists": False,
            "status_json_valid": False,
        }

    raw = {}
    json_valid = False
    try:
        raw = _load_json_text(status_path)
        json_valid = True
    except Exception:
        raw = {}

    sections = raw.get("sections", {}) if isinstance(raw, dict) else {}
    extensions = sections.get("extensions", {}) if isinstance(sections, dict) else {}
    quality_gate = sections.get("quality_gate", {}) if isinstance(sections, dict) else {}
    readiness = sections.get("readiness", {}) if isinstance(sections, dict) else {}
    isolation = extensions.get("isolation_summary", {}) if isinstance(extensions, dict) else {}

    overall_status = str(raw.get("overall_status", "MISSING")).strip().upper()
    extensions_single_gate_status = str(extensions.get("single_gate_status", "MISSING")).strip().upper()
    extensions_registry_status = str(extensions.get("registry_status", "MISSING")).strip().upper()
    extensions_isolation_status = str(isolation.get("status", "MISSING")).strip().upper()
    quality_gate_status = str(quality_gate.get("status", "MISSING")).strip().upper()
    readiness_status = str(readiness.get("status", "MISSING")).strip().upper()

    risk_score = (
        _risk_weight(overall_status)
        + _risk_weight(extensions_single_gate_status)
        + _risk_weight(extensions_registry_status)
        + _risk_weight(extensions_isolation_status)
        + _risk_weight(quality_gate_status)
        + _risk_weight(readiness_status)
    )

    return {
        "overall_status": overall_status,
        "extensions_single_gate_status": extensions_single_gate_status,
        "extensions_registry_status": extensions_registry_status,
        "extensions_isolation_status": extensions_isolation_status,
        "quality_gate_status": quality_gate_status,
        "readiness_status": readiness_status,
        "risk_score": int(risk_score),
        "risk_level": _risk_level(risk_score),
        "status_path": str(status_path),
        "status_exists": True,
        "status_json_valid": bool(json_valid),
    }


def _repo_is_critical(repo_payload: dict[str, Any]) -> bool:
    check_statuses = [
        repo_payload.get("overall_status"),
        repo_payload.get("extensions_single_gate_status"),
        repo_payload.get("extensions_registry_status"),
        repo_payload.get("extensions_isolation_status"),
        repo_payload.get("quality_gate_status"),
        repo_payload.get("readiness_status"),
    ]
    return any(str(x).upper() in RISK_CRITICAL_STATUSES or str(x).upper() == "WARN" for x in check_statuses)


def _load_manifest_entries(data: Any, manifest_root: Path) -> list[RepoContext]:
    if not isinstance(data, dict):
        return []

    raw_rows = data.get("repos")
    if not isinstance(raw_rows, list):
        raw_rows = data.get("managed_repos")
    if not isinstance(raw_rows, list):
        raw_rows = data.get("entries")
    if not isinstance(raw_rows, list):
        return []

    entries: list[RepoContext] = []
    for row in raw_rows:
        if isinstance(row, str):
            row = {"repo_root": row}
        if not isinstance(row, dict):
            continue

        repo_raw = str(row.get("repo_root") or row.get("repo") or "").strip()
        if not repo_raw:
            continue
        try:
            repo_root = Path(repo_raw).expanduser().resolve()
        except Exception:
            continue

        workspace_raw = str(
            row.get("workspace_root")
            or row.get("workspace")
            or row.get("ws_root")
            or row.get("workspace_path")
            or ""
        ).strip()
        if workspace_raw:
            ws_path = Path(workspace_raw).expanduser()
            if not ws_path.is_absolute():
                ws_path = (manifest_root / ws_path).resolve()
        else:
            ws_path = Path()
        repo_slug = str(row.get("repo_slug") or row.get("slug") or repo_root.name).strip()
        repo_id = str(row.get("repo_id") or row.get("id") or row.get("repo") or "").strip()
        force_critical = parse_bool(row.get("critical"), default=False)
        if not repo_id:
            repo_id = _safe_slug(repo_slug)[:24] or _hash_tag(repo_root)

        entries.append(
            RepoContext(
                repo_root=repo_root,
                workspace_root=ws_path,
                repo_slug=repo_slug or _safe_slug(repo_root.name),
                repo_id=repo_id,
                source="manifest",
                missing_workspace=_is_workspace_placeholder(ws_path),
                force_critical=force_critical,
            )
        )

    return entries


def _manifest_path_from_prefix(prefix: Path) -> Path:
    return (prefix / ".cache" / "managed_repos.v1.json").resolve()


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = _load_json_text(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_repo_list(
    orchestrator_root: Path,
    managed_roots: list[str],
    manifest_path: Path | None,
    workspace_root_prefix: Path | None,
    include_self: bool,
    managed_roots_critical: bool,
) -> list[RepoContext]:
    normalized: dict[str, RepoContext] = {}

    manifest_entries: list[RepoContext] = []
    manifest_base = orchestrator_root
    if manifest_path is not None:
        manifest_payload = _load_manifest(manifest_path)
        manifest_base = manifest_path.parent.resolve()
        manifest_entries = _load_manifest_entries(manifest_payload, manifest_base)
        for entry in manifest_entries:
            key = str(entry.repo_root.resolve())
            normalized[key] = entry
    elif workspace_root_prefix is not None:
        auto_manifest = _manifest_path_from_prefix(workspace_root_prefix)
        if auto_manifest.exists():
            manifest_payload = _load_manifest(auto_manifest)
            manifest_base = auto_manifest.parent.resolve()
            manifest_entries = _load_manifest_entries(manifest_payload, manifest_base)
            for entry in manifest_entries:
                key = str(entry.repo_root.resolve())
                normalized[key] = entry

    if managed_roots:
        for item in managed_roots:
            item = str(item).strip()
            if not item:
                continue
            try:
                repo_root = Path(item).expanduser().resolve()
            except Exception:
                continue
            key = str(repo_root)
            existing = normalized.get(key)
            existing_workspace = existing.workspace_root if isinstance(existing, RepoContext) else Path()
            if _is_workspace_placeholder(existing_workspace):
                existing_workspace = Path()
            existing_force_critical = bool(existing.force_critical) if isinstance(existing, RepoContext) else False
            existing_repo_slug = (
                existing.repo_slug if isinstance(existing, RepoContext) and str(existing.repo_slug).strip() else _safe_slug(repo_root.name)
            )
            existing_repo_id = (
                existing.repo_id if isinstance(existing, RepoContext) and str(existing.repo_id).strip() else _hash_tag(repo_root)
            )
            merged_source = "managed-root" if not isinstance(existing, RepoContext) else f"{existing.source}+managed-root"
            merged_force_critical = bool(managed_roots_critical or existing_force_critical)

            if not repo_root.exists() or not repo_root.is_dir():
                # Missing repo root keeps visibility in report but commands are not executed.
                repo = RepoContext(
                    repo_root=repo_root,
                    workspace_root=existing_workspace if not _is_workspace_placeholder(existing_workspace) else Path("/missing"),
                    repo_slug=existing_repo_slug,
                    repo_id=existing_repo_id,
                    source=merged_source,
                    notes=["repo_root_missing"],
                    missing_workspace=True,
                    force_critical=merged_force_critical,
                )
            else:
                repo = RepoContext(
                    repo_root=repo_root,
                    workspace_root=existing_workspace if not _is_workspace_placeholder(existing_workspace) else Path(),
                    repo_slug=existing_repo_slug,
                    repo_id=existing_repo_id,
                    source=merged_source,
                    missing_workspace=True,
                    force_critical=merged_force_critical,
                )
            normalized[key] = repo

    ordered: list[RepoContext] = list(normalized.values())
    ordered.sort(key=lambda item: str(item.repo_root).lower())

    if include_self:
        key = str(orchestrator_root.resolve())
        if key not in normalized:
            ordered.append(
                RepoContext(
                    repo_root=orchestrator_root,
                    workspace_root=(orchestrator_root / ".cache" / "ws_customer_default"),
                    repo_slug="orchestrator",
                    repo_id="orchestrator-self",
                    source="self",
                    force_critical=False,
                )
            )

    if workspace_root_prefix is not None:
        for idx, item in enumerate(ordered, start=1):
            if not _is_workspace_placeholder(item.workspace_root):
                continue
            item.workspace_root = (
                workspace_root_prefix
                / f"repo-{idx}-{_safe_slug(item.repo_slug)}-{_hash_tag(item.repo_root)}"
            ).resolve()

    # Fill missing repo_id when empty
    for item in ordered:
        if not item.repo_id:
            item.repo_id = _hash_tag(item.repo_root)
    return ordered


def _run_manage_command(
    orchestrator_root: Path,
    command: str,
    args: list[str],
    timeout_seconds: int | None,
    workspace_root: Path,
) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "src.ops.manage", command, *args]
    started_at = datetime.now(timezone.utc)
    proc = subprocess.run(
        cmd,
        cwd=str(orchestrator_root),
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    ended_at = datetime.now(timezone.utc)
    raw_stdout = proc.stdout or ""
    raw_stderr = proc.stderr or ""

    payload = _extract_json_payload(raw_stdout)
    if payload is None and raw_stderr:
        payload = _extract_json_payload(raw_stderr)

    status = ""
    if isinstance(payload, dict):
        status = str(payload.get("status", "")).strip().upper()
    if not status:
        status = _extract_status_from_text(f"{raw_stdout}\n{raw_stderr}")
    if not status:
        status = "OK" if proc.returncode == 0 else "FAIL"
    if proc.returncode != 0 and status in {"OK", "WARN", "IDLE", "SKIPPED", "REPORT"}:
        status = "FAIL"

    payload_obj = payload if isinstance(payload, dict) else {"status": status}
    blocker = _classify_command_issue(
        command=command,
        status=status,
        return_code=proc.returncode,
        payload=payload_obj,
        stdout=raw_stdout,
        stderr=raw_stderr,
    )

    elapsed = max(0.0, (ended_at - started_at).total_seconds())
    return {
        "command": command,
        "args": args,
        "return_code": proc.returncode,
        "status": status,
        "elapsed_seconds": round(elapsed, 3),
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": ended_at.isoformat().replace("+00:00", "Z"),
        "stdout": raw_stdout.strip(),
        "stderr": raw_stderr.strip(),
        "evidence_paths": _collect_evidence(
            payload_obj,
            workspace_root,
            fallback_root=orchestrator_root,
        ),
        "payload": payload_obj,
        "blocker": blocker,
    }


def _build_steps(phase: str) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = []
    if phase in {"1", "2", "3", "all"}:
        steps.extend(
            [
                ("extension-registry", ["--mode", "report", "--chat", "false"]),
                ("extension-help", ["--detail", "false", "--chat", "false"]),
            ]
        )
    if phase in {"2", "3", "all"}:
        steps.extend(
            [
                ("doc-nav-check", ["--detail", "false", "--strict", "false", "--chat", "false"]),
                ("work-intake-check", ["--mode", "report", "--detail", "false", "--chat", "false"]),
            ]
        )
    if phase in {"3", "all"}:
        steps.extend(
            [
                ("policy-check", ["--source", "both", "--outdir", ""]),
                ("script-budget", ["--out", ""]),
                ("smoke", ["--level", "fast"]),
            ]
        )
    # system-status is always useful for final gate/risk snapshot.
    steps.append(("system-status", ["--dry-run", "false"]))
    # normalize non-workspace commands (policy-check, script-budget, smoke) to workspace-specific paths.
    return steps


def _normalize_steps_for_workspace(
    steps: list[tuple[str, list[str]]],
    *,
    workspace_root: Path,
    orchestrator_root: Path,
    repo_id: str,
) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    ws_abs = str(workspace_root)
    safe_repo_id = _safe_slug(str(repo_id or "").strip() or "repo")
    run_out_root = (orchestrator_root / ".cache" / "project_management" / safe_repo_id).resolve()
    for command, args in steps:
        normalized: list[str] = []
        for item in args:
            if item == "":  # for workspace-specific defaults
                continue
            normalized.append(item)
        if command in {"extension-registry", "extension-help", "doc-nav-check", "work-intake-check", "system-status"}:
            normalized = ["--workspace-root", ws_abs, *normalized]
        if command == "policy-check":
            normalized = ["--outdir", str(run_out_root / "policy_check")]
        if command == "script-budget":
            normalized = ["--out", str(run_out_root / "script_budget" / "report.json")]
        if command == "smoke":
            normalized = [*normalized, "--root-cause-out", str(run_out_root / "smoke_root_cause_report.v1.json")]
        out.append((command, normalized))
    return out


_BLOCKER_TAXONOMY: dict[str, dict[str, str]] = {
    "NONE": {"category": "NONE", "severity": "INFO", "summary": "No blocker."},
    "OUTPUT_PATH_OUTSIDE_REPO": {
        "category": "CONFIG",
        "severity": "HIGH",
        "summary": "Command output path is outside orchestrator repository boundary.",
    },
    "POLICY_DEPRECATION_GATE": {
        "category": "POLICY",
        "severity": "HIGH",
        "summary": "Policy deprecation warning threshold gate exceeded.",
    },
    "POLICY_CHECK_FAIL": {
        "category": "POLICY",
        "severity": "HIGH",
        "summary": "Policy check command failed.",
    },
    "SCRIPT_BUDGET_GROWTH": {
        "category": "MAINTAINABILITY",
        "severity": "HIGH",
        "summary": "Script budget no-growth/hard limit violated.",
    },
    "SCRIPT_BUDGET_FAIL": {
        "category": "MAINTAINABILITY",
        "severity": "HIGH",
        "summary": "Script budget command failed.",
    },
    "SCRIPT_BUDGET_WARN": {
        "category": "MAINTAINABILITY",
        "severity": "MEDIUM",
        "summary": "Script budget warning threshold triggered.",
    },
    "DOC_NAV_WARN": {
        "category": "DOCS",
        "severity": "MEDIUM",
        "summary": "Doc navigation warning surfaced.",
    },
    "DOC_NAV_FAIL": {
        "category": "DOCS",
        "severity": "HIGH",
        "summary": "Doc navigation command failed.",
    },
    "WORK_INTAKE_WARN": {
        "category": "INTAKE",
        "severity": "MEDIUM",
        "summary": "Work intake check produced warning.",
    },
    "WORK_INTAKE_FAIL": {
        "category": "INTAKE",
        "severity": "HIGH",
        "summary": "Work intake check failed.",
    },
    "SMOKE_FAIL": {
        "category": "SMOKE",
        "severity": "HIGH",
        "summary": "Smoke command failed without classified root cause.",
    },
    "COMMAND_WARN": {
        "category": "GENERAL",
        "severity": "LOW",
        "summary": "Command completed with warning status.",
    },
    "COMMAND_FAIL": {
        "category": "GENERAL",
        "severity": "HIGH",
        "summary": "Command failed.",
    },
}

_SEVERITY_ORDER = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1, "UNKNOWN": 0}


def _extract_error_code_from_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    patterns = (
        r"\berror_code=([A-Z0-9_]+)\b",
        r'"error_code"\s*:\s*"([A-Z0-9_]+)"',
        r"\broot_error_code=([A-Z0-9_]+)\b",
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        code = str(m.group(1) or "").strip().upper()
        if code:
            return code
    return ""


def _blocker_meta(code: str, *, command: str, payload: dict[str, Any], status: str) -> dict[str, str]:
    normalized = str(code or "").strip().upper() or "COMMAND_FAIL"
    if normalized.startswith("SMOKE_"):
        root_sev = str(payload.get("root_error_severity") or "").strip().upper()
        sev = root_sev if root_sev in _SEVERITY_ORDER else "HIGH"
        category = "SMOKE"
        return {
            "code": normalized,
            "category": category,
            "severity": sev,
            "summary": "Smoke step failed with classified root cause.",
        }
    base = _BLOCKER_TAXONOMY.get(normalized)
    if isinstance(base, dict):
        return {
            "code": normalized,
            "category": str(base.get("category") or "GENERAL"),
            "severity": str(base.get("severity") or "HIGH"),
            "summary": str(base.get("summary") or ""),
        }
    fallback = "COMMAND_WARN" if status == "WARN" else "COMMAND_FAIL"
    base = _BLOCKER_TAXONOMY[fallback]
    return {
        "code": fallback,
        "category": str(base.get("category") or "GENERAL"),
        "severity": str(base.get("severity") or "HIGH"),
        "summary": str(base.get("summary") or ""),
    }


def _classify_command_issue(
    *,
    command: str,
    status: str,
    return_code: int,
    payload: dict[str, Any],
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    status_u = str(status or "").strip().upper()
    if status_u not in {"WARN", "FAIL", "ERROR", "BLOCKED"}:
        meta = _blocker_meta("NONE", command=command, payload=payload, status=status_u)
        return {
            "status": status_u or "OK",
            "return_code": int(return_code),
            "error_code": "",
            "blocker_code": meta["code"],
            "blocker_category": meta["category"],
            "blocker_severity": meta["severity"],
            "blocker_summary": meta["summary"],
            "source": "status_ok",
        }

    text = "\n".join([str(stdout or ""), str(stderr or "")]).strip()
    payload_error_code = str(payload.get("error_code") or "").strip().upper()
    if command == "smoke":
        payload_error_code = str(payload.get("root_error_code") or payload_error_code).strip().upper()
    text_error_code = _extract_error_code_from_text(text)
    error_code = payload_error_code or text_error_code
    code = ""
    source = ""

    if "PATH_OUTSIDE_REPO" in text or "is not in the subpath of" in text:
        code = "OUTPUT_PATH_OUTSIDE_REPO"
        source = "stderr:path_outside_repo"
    elif command == "policy-check":
        gate_exceeded = bool(payload.get("deprecation_gate_exceeded"))
        if gate_exceeded or "DEPRECATION_GATE_EXCEEDED" in text:
            code = "POLICY_DEPRECATION_GATE"
            source = "policy_gate"
        else:
            code = "POLICY_CHECK_FAIL"
            source = "policy_fallback"
    elif command == "script-budget":
        if "PY_FILE_NO_GROWTH" in text or "PY_FILE_GROWTH_FORBIDDEN" in text:
            code = "SCRIPT_BUDGET_GROWTH"
            source = "script_budget_growth"
        elif status_u == "WARN":
            code = "SCRIPT_BUDGET_WARN"
            source = "script_budget_warn"
        else:
            code = "SCRIPT_BUDGET_FAIL"
            source = "script_budget_fallback"
    elif command == "smoke":
        if error_code:
            code = f"SMOKE_{error_code}"
            source = "smoke_root_error_code"
        else:
            code = "SMOKE_FAIL"
            source = "smoke_fallback"
    elif command == "doc-nav-check":
        code = "DOC_NAV_WARN" if status_u == "WARN" else "DOC_NAV_FAIL"
        source = "doc_nav_status"
    elif command == "work-intake-check":
        code = "WORK_INTAKE_WARN" if status_u == "WARN" else "WORK_INTAKE_FAIL"
        source = "work_intake_status"
    else:
        code = "COMMAND_WARN" if status_u == "WARN" else "COMMAND_FAIL"
        source = "default"

    meta = _blocker_meta(code, command=command, payload=payload, status=status_u)
    return {
        "status": status_u or "FAIL",
        "return_code": int(return_code),
        "error_code": error_code or "",
        "blocker_code": meta["code"],
        "blocker_category": meta["category"],
        "blocker_severity": meta["severity"],
        "blocker_summary": meta["summary"],
        "source": source,
    }


def _build_summary(entries: list[dict[str, Any]], critical_only: bool) -> dict[str, Any]:
    selected = [entry for entry in entries if (not critical_only or bool(entry.get("critical")))]
    all_count = len(entries)
    selected_count = len(selected)
    all_critical = sum(1 for entry in entries if bool(entry.get("critical")))
    selected_critical = sum(1 for entry in selected if bool(entry.get("critical")))

    def _safe_status_count(field: str) -> dict[str, int]:
        out = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in selected if critical_only else entries:
            level = str(item.get(field, "LOW")).upper()
            if level not in out:
                level = "LOW"
            out[level] += 1
        return out

    all_risk = _safe_status_count("risk_level")
    selected_risk = _safe_status_count("risk_level")
    all_risk_score = sum(int(item.get("risk_score", 0) or 0) for item in entries)
    selected_risk_score = sum(int(item.get("risk_score", 0) or 0) for item in selected)
    selected_risk_avg = round(selected_risk_score / selected_count, 2) if selected_count else 0.0
    return {
        "all_entries_count": all_count,
        "selected_entries_count": selected_count,
        "critical_only": bool(critical_only),
        "all_critical_count": all_critical,
        "selected_critical_count": selected_critical,
        "all_risk_score": all_risk_score,
        "selected_risk_score": selected_risk_score,
        "selected_risk_score_avg": selected_risk_avg,
        "all_risk_level_counts": all_risk,
        "selected_risk_level_counts": selected_risk,
        "risk_line": (
            f"all={all_count} selected={selected_count} "
            f"critical={selected_critical}/{all_critical} "
            f"risk_score={selected_risk_score} risk_avg={selected_risk_avg:.2f} "
            f"levels(Critical/High/Medium/Low)="
            f"{selected_risk['CRITICAL']}/{selected_risk['HIGH']}/{selected_risk['MEDIUM']}/{selected_risk['LOW']}"
        ),
    }


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
        "generated_at": now_iso(),
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
        "generated_at": now_iso(),
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


def _run_repo_pipeline(
    orchestrator_root: Path,
    ctx: RepoContext,
    phase: str,
    stop_on_fail: bool,
    timeout_seconds: int | None,
    bootstrap_workspace: bool,
    print_evidence_map: bool,
) -> dict[str, Any]:
    if not ctx.repo_root.exists() or not ctx.repo_root.is_dir():
        return {
            "repo_root": str(ctx.repo_root),
            "workspace_root": str(ctx.workspace_root),
            "repo_slug": ctx.repo_slug,
            "repo_id": ctx.repo_id,
            "source": ctx.source,
            "status": "FAIL",
            "error_code": "REPO_ROOT_MISSING",
            "steps": [],
            "repo_status": {
                "overall_status": "MISSING",
                "extensions_single_gate_status": "MISSING",
                "extensions_registry_status": "MISSING",
                "extensions_isolation_status": "MISSING",
                "quality_gate_status": "MISSING",
                "readiness_status": "MISSING",
                "risk_score": 3,
                "risk_level": "MEDIUM",
            },
            "critical": True,
            "evidence_paths": [],
            "notes": ["repo_root_missing"],
        }

    if not ctx.workspace_root.exists():
        if bootstrap_workspace:
            ctx.workspace_root.mkdir(parents=True, exist_ok=True)
            (ctx.workspace_root / ".cache").mkdir(parents=True, exist_ok=True)
            (ctx.workspace_root / "policies").mkdir(parents=True, exist_ok=True)
            ctx.notes.append("workspace_bootstrapped")
        else:
            return {
                "repo_root": str(ctx.repo_root),
                "workspace_root": str(ctx.workspace_root),
                "repo_slug": ctx.repo_slug,
                "repo_id": ctx.repo_id,
                "source": ctx.source,
                "status": "FAIL",
                "error_code": "WORKSPACE_ROOT_MISSING",
                "steps": [],
                "repo_status": {
                    "overall_status": "MISSING",
                    "extensions_single_gate_status": "MISSING",
                    "extensions_registry_status": "MISSING",
                    "extensions_isolation_status": "MISSING",
                    "quality_gate_status": "MISSING",
                    "readiness_status": "MISSING",
                    "risk_score": 3,
                    "risk_level": "MEDIUM",
                },
                "critical": True,
                "evidence_paths": [],
                "notes": ["workspace_root_missing"],
            }

    steps = _normalize_steps_for_workspace(
        _build_steps(phase),
        workspace_root=ctx.workspace_root,
        orchestrator_root=orchestrator_root,
        repo_id=ctx.repo_id,
    )
    execution_results = []
    failed = False
    evidence_paths: list[str] = []
    command_issues: list[dict[str, str]] = []

    for step_name, args in steps:
        started = now_iso()
        step_result = _run_manage_command(
            orchestrator_root=orchestrator_root,
            command=step_name,
            args=args,
            timeout_seconds=timeout_seconds,
            workspace_root=ctx.workspace_root,
        )
        step_result["started_at"] = started
        step_result["command_group"] = "project_management"
        execution_results.append(step_result)
        evidence_paths.extend(step_result.get("evidence_paths") or [])
        status = str(step_result.get("status", "FAIL")).upper()
        if step_name in CRITICAL_COMMANDS and status in {"WARN", "FAIL", "ERROR", "BLOCKED"}:
            blocker = step_result.get("blocker") if isinstance(step_result.get("blocker"), dict) else {}
            command_issues.append(
                {
                    "command": step_name,
                    "status": status,
                    "return_code": str(step_result.get("return_code", "")),
                    "error_code": str(blocker.get("error_code") or "").strip(),
                    "blocker_code": str(blocker.get("blocker_code") or "").strip(),
                    "blocker_category": str(blocker.get("blocker_category") or "").strip(),
                    "blocker_severity": str(blocker.get("blocker_severity") or "").strip(),
                    "source": str(blocker.get("source") or "").strip(),
                }
            )
        if status in {"FAIL", "ERROR", "BLOCKED"}:
            failed = True
            if stop_on_fail:
                break

    repo_status = _build_repo_status(ctx.workspace_root)
    repo_status.update(
        {
            "repo_root": str(ctx.repo_root),
            "workspace_root": str(ctx.workspace_root),
            "repo_slug": ctx.repo_slug,
            "repo_id": ctx.repo_id,
            "source": ctx.source,
        }
    )

    if failed:
        overall = "FAIL"
    elif any(str(s.get("status", "")).upper() == "WARN" for s in execution_results):
        overall = "WARN"
    else:
        overall = str(repo_status.get("overall_status", "OK")).upper() or "OK"
        if overall not in {"OK", "IDLE", "WARN"}:
            # Keep strictness consistent with cockpit-like gates.
            if overall in RISK_CRITICAL_STATUSES:
                overall = "FAIL"
            else:
                overall = "WARN"

    risk_level = str(repo_status.get("risk_level", "LOW")).upper()
    critical = bool(ctx.force_critical) or _repo_is_critical(repo_status)
    if print_evidence_map is False:
        for step in execution_results:
            step.pop("stdout", None)
            step.pop("stderr", None)
            step["payload"] = _compact_step_payload(step.get("payload"))
    else:
        # Keep stdout short while still exposing evidence references.
        for step in execution_results:
            if isinstance(step.get("stdout"), str):
                step["stdout"] = step["stdout"].splitlines()[:8]

    note_values = {*ctx.notes, f"critical={critical}", f"risk_level={risk_level}"}
    if ctx.force_critical:
        note_values.add("critical_forced=true")

    return {
        "repo_root": str(ctx.repo_root),
        "workspace_root": str(ctx.workspace_root),
        "repo_slug": ctx.repo_slug,
        "repo_id": ctx.repo_id,
        "source": ctx.source,
        "status": overall,
        "critical": critical,
        "risk_score": int(repo_status.get("risk_score", 0) or 0),
        "risk_level": risk_level,
        "system_status": repo_status.get("overall_status"),
        "gates": {
            "overall": repo_status.get("overall_status"),
            "extensions": {
                "single_gate_status": repo_status.get("extensions_single_gate_status"),
                "registry_status": repo_status.get("extensions_registry_status"),
                "isolation_status": repo_status.get("extensions_isolation_status"),
            },
            "quality_gate": repo_status.get("quality_gate_status"),
            "readiness": repo_status.get("readiness_status"),
        },
        "command_issues": command_issues,
        "notes": sorted(note_values),
        "steps": execution_results,
        "evidence_paths": sorted(set(str(p) for p in evidence_paths if isinstance(p, str))),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run project management phases across multiple repositories."
    )
    parser.add_argument("--orchestrator-root", required=True)
    parser.add_argument(
        "--managed-repo-root",
        action="append",
        default=[],
        metavar="PATH",
        help="One managed repo path (repeatable).",
    )
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--workspace-root-prefix", default="")
    parser.add_argument(
        "--phase",
        default="all",
        choices=["1", "2", "3", "all"],
        help="Phase set: 1, 2, 3 or all.",
    )
    parser.add_argument("--critical-only", default="false")
    parser.add_argument(
        "--managed-roots-critical",
        default="false",
        help="true|false. If true, repos passed via --managed-repo-root are always counted as critical.",
    )
    parser.add_argument("--print-evidence-map", default="true")
    parser.add_argument("--stop-on-fail", default="false")
    parser.add_argument("--bootstrap-workspace", default="true")
    parser.add_argument("--include-self", default="false")
    parser.add_argument("--command-timeout", default="600")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    orchestrator_root = Path(str(args.orchestrator_root)).resolve()
    if not orchestrator_root.exists() or not orchestrator_root.is_dir():
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "ORCHESTRATOR_ROOT_INVALID",
                    "orchestrator_root": str(args.orchestrator_root),
                    "generated_at": now_iso(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    manifest_path = None
    if str(args.manifest_path).strip():
        manifest_path = Path(str(args.manifest_path)).expanduser().resolve()
        if not manifest_path.exists():
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "error_code": "MANIFEST_NOT_FOUND",
                        "manifest_path": str(manifest_path),
                        "generated_at": now_iso(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

    workspace_root_prefix = (
        Path(str(args.workspace_root_prefix)).expanduser().resolve()
        if str(args.workspace_root_prefix).strip()
        else None
    )
    if workspace_root_prefix is None:
        workspace_root_prefix = orchestrator_root / ".cache" / "ws_customer_default_multi2"

    managed_repos = _build_repo_list(
        orchestrator_root=orchestrator_root,
        managed_roots=[str(item) for item in args.managed_repo_root],
        manifest_path=manifest_path,
        workspace_root_prefix=workspace_root_prefix,
        include_self=parse_bool(args.include_self, default=False),
        managed_roots_critical=parse_bool(args.managed_roots_critical, default=False),
    )

    if not managed_repos:
        managed_repos = [
            RepoContext(
                repo_root=orchestrator_root,
                workspace_root=(
                    workspace_root_prefix
                    / ".cache"
                    / "ws_customer_default_multi2_orchestrator"
                    if workspace_root_prefix is not None
                    else orchestrator_root / ".cache" / "ws_customer_default"
                ),
                repo_slug="orchestrator",
                repo_id="orchestrator",
                source="fallback",
            )
        ]

    if parse_bool(args.bootstrap_workspace, default=True):
        workspace_root_prefix.mkdir(parents=True, exist_ok=True)

    all_results: list[dict[str, Any]] = []
    run_failed = False
    timeout_seconds: int | None
    try:
        value = int(str(args.command_timeout).strip())
        timeout_seconds = value if value > 0 else None
    except Exception:
        timeout_seconds = None

    critical_only = parse_bool(args.critical_only, default=False)
    print_evidence_map = parse_bool(args.print_evidence_map, default=True)
    stop_on_fail = parse_bool(args.stop_on_fail, default=False)
    phase = str(args.phase).strip()

    for repo_ctx in managed_repos:
        if parse_bool(args.bootstrap_workspace, default=True) and repo_ctx.workspace_root:
            repo_ctx.workspace_root = repo_ctx.workspace_root.expanduser().resolve()
        result = _run_repo_pipeline(
            orchestrator_root=orchestrator_root,
            ctx=repo_ctx,
            phase=phase,
            stop_on_fail=stop_on_fail,
            timeout_seconds=timeout_seconds,
            bootstrap_workspace=parse_bool(args.bootstrap_workspace, default=True),
            print_evidence_map=print_evidence_map,
        )
        all_results.append(result)
        if str(result.get("status", "")).upper() in {"FAIL", "ERROR"}:
            run_failed = True
            if stop_on_fail:
                break

    summary = _build_summary(all_results, critical_only=critical_only)
    extension_issue_summary = _build_extension_issue_summary(all_results)
    blocking_reasons = _build_blocking_reasons(all_results)
    smoke_root_cause_aggregation = _build_smoke_root_cause_aggregation(all_results)
    report = {
        "status": "FAIL" if run_failed else "OK",
        "generated_at": now_iso(),
        "orchestrator_root": str(orchestrator_root),
        "phase": phase,
        "critical_only": critical_only,
        "print_evidence_map": print_evidence_map,
        "workspace_root_prefix": str(workspace_root_prefix) if workspace_root_prefix else "",
        "summary": summary,
        "extension_issue_summary": extension_issue_summary,
        "blocking_reasons": blocking_reasons,
        "smoke_root_cause_aggregation": smoke_root_cause_aggregation,
        "repos": all_results if not critical_only else [entry for entry in all_results if bool(entry.get("critical"))],
        "all_repos": all_results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if run_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
