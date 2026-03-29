"""Context profile resolver — resolves active profile from registry.

Reads policy_context_profile_registry.v1.json, evaluates trigger_conditions
against available context, and writes active_context_profile.v1.json.

Usage (CLI):
    python -m src.ops.manage context-profile-check --workspace-root .cache/ws_customer_default
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.shared.utils import load_json, write_json_atomic

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_profile_registry() -> dict[str, Any]:
    """Load profile registry policy from canonical path."""
    path = _REPO_ROOT / "policies" / "policy_context_profile_registry.v1.json"
    if not path.exists():
        return {"profiles": [], "default_profile": "TASK_EXECUTION"}
    return load_json(path)


def _gather_context_signals(workspace_root: Path) -> dict[str, Any]:
    """Gather context signals for trigger condition evaluation."""
    signals: dict[str, Any] = {}

    # System status
    status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    if status_path.exists():
        try:
            status = load_json(status_path)
            signals["system_status"] = {"overall_status": status.get("status", "OK")}
        except Exception:
            pass

    # Integrity
    integrity_path = workspace_root / ".cache" / "reports" / "integrity_report.v1.json"
    if integrity_path.exists():
        try:
            integrity = load_json(integrity_path)
            violations = integrity.get("violations", [])
            signals["integrity"] = {"violation_count": len(violations)}
        except Exception:
            pass
    else:
        signals["integrity"] = {"violation_count": 0}

    # Session
    session_path = workspace_root / ".cache" / "reports" / "session_status.v1.json"
    signals["session"] = {
        "context_loaded": session_path.exists(),
        "mode": "ops_command",
    }

    return signals


def _eval_condition(condition: dict[str, Any], signals: dict[str, Any]) -> bool:
    """Evaluate a single mini-DSL trigger condition against signals."""
    op = condition.get("op", "")
    left_ref = condition.get("left", {})
    right = condition.get("right")

    # Resolve variable reference
    var_path = left_ref.get("var", "") if isinstance(left_ref, dict) else ""
    parts = var_path.split(".")
    value: Any = signals
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    if op == "eq":
        return value == right
    elif op == "gt":
        try:
            return float(value) > float(right)
        except (TypeError, ValueError):
            return False
    elif op == "in":
        return value in (right if isinstance(right, list) else [right])
    elif op == "truthy":
        return bool(value)

    return False


def resolve_profile(
    workspace_root: Path,
    *,
    explicit_profile: str | None = None,
    agent_id: str = "claude",
) -> dict[str, Any]:
    """Resolve which context profile is active for this workspace.

    Resolution order: explicit > auto (trigger match) > default.
    """
    registry = _load_profile_registry()
    profiles = registry.get("profiles", [])
    default_id = registry.get("default_profile", "TASK_EXECUTION")

    # Explicit override
    if explicit_profile:
        for p in profiles:
            if p.get("profile_id") == explicit_profile:
                return _build_result(p, "explicit", workspace_root, agent_id)
        return _build_result(None, "fallback", workspace_root, agent_id, profile_id=default_id)

    # Auto: evaluate trigger conditions
    signals = _gather_context_signals(workspace_root)

    for profile in profiles:
        conditions = profile.get("trigger_conditions", [])
        if not conditions:
            continue
        for cond in conditions:
            if _eval_condition(cond, signals):
                return _build_result(profile, "auto", workspace_root, agent_id, matched_trigger=str(cond.get("op", "")))

    # Default fallback
    for p in profiles:
        if p.get("profile_id") == default_id:
            return _build_result(p, "default", workspace_root, agent_id)

    return _build_result(None, "fallback", workspace_root, agent_id, profile_id=default_id)


def _build_result(
    profile: dict[str, Any] | None,
    method: str,
    workspace_root: Path,
    agent_id: str,
    *,
    profile_id: str | None = None,
    matched_trigger: str | None = None,
) -> dict[str, Any]:
    pid = profile.get("profile_id") if profile else profile_id or "TASK_EXECUTION"
    result = {
        "version": "v1",
        "profile_id": pid,
        "activated_at": _now_iso(),
        "resolution_method": method,
        "workspace_root": str(workspace_root),
        "agent_id": agent_id,
        "bootstrap_commands": profile.get("bootstrap_commands", []) if profile else [],
        "required_files": profile.get("required_files", []) if profile else [],
        "sections": profile.get("sections", {}) if profile else {},
        "tags": profile.get("tags", []) if profile else [],
    }
    if matched_trigger:
        result["matched_trigger"] = matched_trigger
    return result


def write_active_profile(workspace_root: Path, result: dict[str, Any]) -> Path:
    """Write active profile artifact to workspace."""
    out_dir = workspace_root / ".cache" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "active_context_profile.v1.json"
    write_json_atomic(out_path, result)
    return out_path


# ── CLI Integration ──────────────────────────────────────────────

def register_context_profile_check_subcommand(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("context-profile-check", help="Resolve and display active context profile")
    p.add_argument("--workspace-root", required=True)
    p.add_argument("--profile", default=None, help="Force a specific profile (override auto-resolution)")
    p.add_argument("--agent-id", default="claude")
    p.add_argument("--write", action="store_true", help="Write active profile artifact to workspace")
    p.set_defaults(func=_cmd_context_profile_check)


def _cmd_context_profile_check(args: argparse.Namespace) -> int:
    ws = Path(args.workspace_root).expanduser().resolve()
    result = resolve_profile(ws, explicit_profile=args.profile, agent_id=args.agent_id)

    if args.write:
        out_path = write_active_profile(ws, result)
        result["artifact_path"] = str(out_path)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
