"""Scope guard — track declared vs actual write scope per session.

Detects scope creep (writing more files or touching more domains than
originally declared) and emits WARN or BLOCK signals.

Thresholds (from policy_scope_guard.v1.json):
  - files > declared * 2 → WARN
  - files > declared * 3 → BLOCK
  - new domain entered   → WARN

State: .cache/reports/scope_guard_state.v1.json (per-session)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.shared.utils import load_json_or_default, now_iso8601, write_json_atomic

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MAX_FILES = 10
_WARN_MULTIPLIER = 2.0
_BLOCK_MULTIPLIER = 3.0


def _state_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "reports" / "scope_guard_state.v1.json"


def _load_state(workspace_root: Path) -> dict[str, Any]:
    return load_json_or_default(_state_path(workspace_root), {})


def _save_state(workspace_root: Path, state: dict[str, Any]) -> None:
    path = _state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, state)


# ── Public API ──────────────────────────────────────────────────


def init_scope(
    workspace_root: Path,
    *,
    session_id: str = "default",
    declared_files: list[str] | None = None,
    max_files: int = _DEFAULT_MAX_FILES,
    declared_domains: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Initialize scope for a session. Called at session start or first write."""
    state = {
        "version": "v1",
        "session_id": session_id,
        "initialized_at": now_iso8601(),
        "updated_at": now_iso8601(),
        "declared_scope": {
            "files": declared_files or [],
            "max_files": max_files,
            "domains": declared_domains or [],
            "description": description,
        },
        "actual_scope": {
            "files_written": [],
            "files_count": 0,
            "domains_touched": [],
        },
        "status": "WITHIN_SCOPE",
        "warnings": [],
        "expanded": False,
    }
    _save_state(workspace_root, state)
    return state


def check_scope(
    workspace_root: Path,
    *,
    new_file: str,
    new_domain: str = "",
) -> dict[str, Any]:
    """Check if writing new_file is within declared scope.

    Returns: {"status": "WITHIN_SCOPE"|"WARN"|"BLOCK", "reason": "...", ...}
    """
    state = _load_state(workspace_root)

    # Auto-init if no state exists
    if not state:
        state = init_scope(workspace_root)

    declared = state.get("declared_scope", {})
    actual = state.get("actual_scope", {})
    max_files = declared.get("max_files", _DEFAULT_MAX_FILES)
    declared_domains = set(declared.get("domains", []))

    # Update actual scope
    files_written = actual.get("files_written", [])
    if new_file not in files_written:
        files_written.append(new_file)
    actual["files_written"] = files_written
    actual["files_count"] = len(files_written)

    domains_touched = set(actual.get("domains_touched", []))
    if new_domain and new_domain != "general":
        domains_touched.add(new_domain)
    actual["domains_touched"] = sorted(domains_touched)

    # Evaluate scope
    warnings: list[str] = list(state.get("warnings", []))
    status = "WITHIN_SCOPE"
    reason = ""

    files_count = actual["files_count"]

    # File count check
    if files_count > max_files * _BLOCK_MULTIPLIER:
        status = "BLOCK"
        reason = f"Scope exceeded: {files_count} files written (max {max_files} * {_BLOCK_MULTIPLIER:.0f} = {int(max_files * _BLOCK_MULTIPLIER)})"
    elif files_count > max_files * _WARN_MULTIPLIER:
        status = "WARN"
        reason = f"Scope growing: {files_count} files (max {max_files} * {_WARN_MULTIPLIER:.0f} = {int(max_files * _WARN_MULTIPLIER)})"
        if reason not in warnings:
            warnings.append(reason)

    # Domain change check
    if declared_domains and new_domain and new_domain not in declared_domains and new_domain != "general":
        domain_warn = f"New domain entered: {new_domain} (declared: {', '.join(sorted(declared_domains))})"
        if domain_warn not in warnings:
            warnings.append(domain_warn)
        if status == "WITHIN_SCOPE":
            status = "WARN"
            reason = domain_warn

    # Update state
    state["actual_scope"] = actual
    state["status"] = status
    state["warnings"] = warnings
    state["updated_at"] = now_iso8601()
    _save_state(workspace_root, state)

    return {
        "status": status,
        "reason": reason,
        "files_written": files_count,
        "max_files": max_files,
        "domains_touched": sorted(domains_touched),
        "warnings_count": len(warnings),
    }


def expand_scope(
    workspace_root: Path,
    *,
    reason: str,
    additional_files: int = 5,
    additional_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Expand scope with user approval. Resets WARN/BLOCK state."""
    state = _load_state(workspace_root)
    if not state:
        return {"status": "ERROR", "reason": "No scope state to expand"}

    declared = state.get("declared_scope", {})
    declared["max_files"] = declared.get("max_files", _DEFAULT_MAX_FILES) + additional_files

    if additional_domains:
        existing = set(declared.get("domains", []))
        existing.update(additional_domains)
        declared["domains"] = sorted(existing)

    state["declared_scope"] = declared
    state["status"] = "WITHIN_SCOPE"
    state["expanded"] = True
    state["warnings"].append(f"Scope expanded: +{additional_files} files, reason: {reason}")
    state["updated_at"] = now_iso8601()

    _save_state(workspace_root, state)
    return {"status": "EXPANDED", "new_max_files": declared["max_files"], "reason": reason}


def get_scope_summary(workspace_root: Path) -> dict[str, Any]:
    """Get current scope state summary."""
    state = _load_state(workspace_root)
    if not state:
        return {"status": "NO_SCOPE", "initialized": False}

    actual = state.get("actual_scope", {})
    declared = state.get("declared_scope", {})
    return {
        "status": state.get("status", "UNKNOWN"),
        "files_written": actual.get("files_count", 0),
        "max_files": declared.get("max_files", _DEFAULT_MAX_FILES),
        "files_remaining": max(0, declared.get("max_files", _DEFAULT_MAX_FILES) - actual.get("files_count", 0)),
        "domains_touched": actual.get("domains_touched", []),
        "warnings_count": len(state.get("warnings", [])),
        "expanded": state.get("expanded", False),
    }
