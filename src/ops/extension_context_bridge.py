"""Extension-context bridge: namespace-isolated decision read/write for extensions.

Extensions access session decisions through this bridge with automatic key prefixing:
  ext:{extension_id}:{key}

This ensures extensions cannot collide with core decisions or other extensions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.session.context_store import (
    SessionContextError,
    SessionPaths,
    load_context,
    save_context_atomic,
    upsert_decision,
)


def _ext_key(extension_id: str, key: str) -> str:
    """Build namespace-prefixed key for extension decisions."""
    return f"ext:{extension_id}:{key}"


def read_extension_decisions(
    *,
    workspace_root: Path,
    extension_id: str,
    session_id: str = "default",
) -> list[dict[str, Any]]:
    """Read decisions belonging to this extension (key prefix: ext:{extension_id}:)."""
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    if not sp.context_path.exists():
        return []

    try:
        ctx = load_context(sp.context_path)
    except SessionContextError:
        return []

    prefix = f"ext:{extension_id}:"
    decisions = ctx.get("ephemeral_decisions", [])
    if not isinstance(decisions, list):
        return []

    return [d for d in decisions if isinstance(d, dict) and str(d.get("key", "")).startswith(prefix)]


def write_extension_decision(
    *,
    workspace_root: Path,
    extension_id: str,
    key: str,
    value: Any,
    session_id: str = "default",
) -> dict[str, Any]:
    """Write a decision on behalf of an extension.

    Key is automatically prefixed: ext:{extension_id}:{key}
    Returns: {status, key, action}
    """
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    full_key = _ext_key(extension_id, key)

    if not sp.context_path.exists():
        return {"status": "SKIP", "key": full_key, "reason": "session_not_found"}

    try:
        ctx = load_context(sp.context_path)
        upsert_decision(ctx, key=full_key, value=value, source="agent")
        save_context_atomic(sp.context_path, ctx)
        return {"status": "OK", "key": full_key, "action": "upserted"}
    except SessionContextError as e:
        return {"status": "FAIL", "key": full_key, "error": e.error_code}
    except Exception as e:
        return {"status": "FAIL", "key": full_key, "error": str(e)[:100]}


def get_context_for_extension(
    *,
    workspace_root: Path,
    extension_id: str,
    session_id: str = "default",
) -> dict[str, Any]:
    """Build context summary for extension consumption.

    Includes: own decisions, shared decisions count, health score, workspace root.
    """
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    summary: dict[str, Any] = {
        "extension_id": extension_id,
        "workspace_root": str(workspace_root),
        "session_id": session_id,
        "own_decisions": [],
        "shared_decisions_count": 0,
        "health_score": None,
    }

    if not sp.context_path.exists():
        return summary

    try:
        ctx = load_context(sp.context_path)
    except SessionContextError:
        return summary

    decisions = ctx.get("ephemeral_decisions", [])
    if isinstance(decisions, list):
        prefix = f"ext:{extension_id}:"
        summary["own_decisions"] = [d for d in decisions if isinstance(d, dict) and str(d.get("key", "")).startswith(prefix)]
        summary["shared_decisions_count"] = len([d for d in decisions if isinstance(d, dict) and not str(d.get("key", "")).startswith("ext:")])

    # Include health score if available
    try:
        from src.benchmark.eval_runner_runtime import _compute_context_health_lens
        health = _compute_context_health_lens(workspace_root=workspace_root, lenses_policy={})
        summary["health_score"] = health.get("score")
    except Exception:
        pass

    return summary


def collect_extension_output_paths(workspace_root: Path) -> list[str]:
    """Collect workspace_reports paths from all enabled extensions in registry."""
    registry_path = workspace_root / ".cache" / "index" / "extension_registry.v1.json"
    if not registry_path.exists():
        return []

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    extensions = data.get("extensions", [])
    if not isinstance(extensions, list):
        return []

    paths: list[str] = []
    for ext in extensions:
        if not isinstance(ext, dict):
            continue
        if not ext.get("enabled", False):
            continue
        outputs = ext.get("outputs", {})
        if isinstance(outputs, dict):
            reports = outputs.get("workspace_reports", [])
            if isinstance(reports, list):
                for r in reports:
                    if isinstance(r, str) and r.strip():
                        paths.append(r.strip())

    return sorted(set(paths))
