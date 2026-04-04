"""Context snapshot — capture full context state for agent handoff.

Creates a portable snapshot of the current context (profile, domain, decisions,
scope, quality) so another agent can resume without context loss.

Usage:
    from src.ops.context_snapshot import create_snapshot
    snap = create_snapshot(workspace_root, from_agent="claude", to_agent="codex")
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from src.shared.utils import load_json_or_default, now_iso8601, write_json_atomic

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def create_snapshot(
    workspace_root: Path,
    *,
    from_agent: str = "claude",
    to_agent: str = "codex",
) -> dict[str, Any]:
    """Create a context snapshot for agent handoff."""
    now = now_iso8601()

    # Active profile
    profile = load_json_or_default(
        workspace_root / ".cache" / "index" / "active_context_profile.v1.json", {}
    )

    # Latest compiled context hash
    compiled = load_json_or_default(
        workspace_root / ".cache" / "reports" / "rule_packet.v1.json", {}
    )
    compiled_hash = hashlib.sha256(
        str(compiled.get("generated_at", "")).encode()
    ).hexdigest()[:12]

    # Scope state
    scope = load_json_or_default(
        workspace_root / ".cache" / "reports" / "scope_guard_state.v1.json", {}
    )

    # Quality metrics
    metrics = load_json_or_default(
        workspace_root / ".cache" / "reports" / "context_session_metrics.v1.json", {}
    )

    # Key decisions from session
    key_decisions = _extract_key_decisions(workspace_root)

    # Pending consultations
    pending = _find_pending_consultations(workspace_root, to_agent)

    # Build snapshot
    snapshot_id = f"SNAP-{now[:10].replace('-', '')}-{compiled_hash[:6]}"

    snapshot = {
        "version": "v1",
        "snapshot_id": snapshot_id,
        "created_at": now,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "compiled_context_hash": compiled_hash,
        "active_profile": profile.get("profile_id", "UNKNOWN"),
        "domain_scope": {
            "primary": compiled.get("rules", {}).get("domain", "general"),
        },
        "key_decisions": key_decisions,
        "scope_state": {
            "status": scope.get("status", "UNKNOWN"),
            "files_written": scope.get("actual_scope", {}).get("files_count", 0),
            "domains_touched": scope.get("actual_scope", {}).get("domains_touched", []),
        },
        "quality_metrics": {
            "cache_hit_rate": metrics.get("cache_hit_rate", 0.0),
            "quality_trend": metrics.get("quality_trend", "STABLE"),
            "total_writes": metrics.get("total_writes", 0),
        },
        "pending_consultations": pending,
    }

    # Write snapshot
    out_path = workspace_root / ".cache" / "reports" / f"{snapshot_id}.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, snapshot)

    return snapshot


def _extract_key_decisions(workspace_root: Path) -> list[dict[str, Any]]:
    """Extract key decisions from the current session."""
    decisions: list[dict[str, Any]] = []
    try:
        from src.session.context_store import SessionPaths, load_context
        sp = SessionPaths(workspace_root=workspace_root, session_id="default")
        if sp.context_path.exists():
            ctx = load_context(sp.context_path)
            for d in ctx.get("ephemeral_decisions", []):
                if isinstance(d, dict):
                    decisions.append({
                        "key": d.get("key", ""),
                        "value": d.get("value"),
                        "source": d.get("source", ""),
                    })
    except Exception:
        pass
    return decisions[:20]  # Cap to prevent bloat


def _find_pending_consultations(workspace_root: Path, to_agent: str) -> list[dict[str, str]]:
    """Find pending consultations addressed to the target agent."""
    pending: list[dict[str, str]] = []
    requests_dir = workspace_root / ".cache" / "index" / "consultations" / "requests"
    if not requests_dir.is_dir():
        return pending
    try:
        for f in sorted(requests_dir.glob("CNS-*.request.v1.json")):
            req = load_json_or_default(f, {})
            if req.get("to_agent") == to_agent and req.get("status") == "OPEN":
                pending.append({
                    "consultation_id": req.get("consultation_id", ""),
                    "topic": req.get("topic", ""),
                    "question": req.get("question", "")[:200],
                })
    except Exception:
        pass
    return pending
