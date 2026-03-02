from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.session.context_store import (
    SessionContextError,
    SessionPaths,
    load_context,
    prune_expired_decisions,
    save_context_atomic,
)


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _decision_key(item: dict[str, Any]) -> tuple[str, float]:
    key = str(item.get("key") or "")
    created = _parse_iso8601(str(item.get("created_at") or ""))
    ts = created.timestamp() if isinstance(created, datetime) else 0.0
    return (key, ts)


def _is_session_expired(ctx: dict[str, Any], now_iso: str) -> bool:
    exp = _parse_iso8601(str(ctx.get("expires_at") or ""))
    now = _parse_iso8601(now_iso)
    if exp is None or now is None:
        return True
    return now > exp


def build_cross_session_context(*, workspace_root: Path, session_name_filter: str = "") -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    now_iso = _now_iso8601()
    sessions_root = workspace_root / ".cache" / "sessions"
    out_path = workspace_root / ".cache" / "index" / "session_cross_context.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    loaded_sessions = 0
    scanned_sessions = 0
    skipped_sessions = 0
    decisions_total = 0
    decisions_by_session: dict[str, int] = {}
    decision_rows: list[dict[str, Any]] = []

    if sessions_root.exists():
        for session_dir in sorted([p for p in sessions_root.iterdir() if p.is_dir()], key=lambda p: p.as_posix()):
            session_id = session_dir.name
            if session_name_filter and session_name_filter not in session_id:
                continue
            scanned_sessions += 1
            sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
            ctx_path = sp.context_path
            if not ctx_path.exists():
                skipped_sessions += 1
                continue
            try:
                ctx = load_context(ctx_path)
            except SessionContextError:
                skipped_sessions += 1
                continue

            if _is_session_expired(ctx, now_iso):
                skipped_sessions += 1
                continue

            before = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            prune_expired_decisions(ctx, now_iso)
            after = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            if before != after:
                try:
                    save_context_atomic(ctx_path, ctx)
                except SessionContextError:
                    pass

            decisions = ctx.get("ephemeral_decisions") if isinstance(ctx.get("ephemeral_decisions"), list) else []
            loaded_sessions += 1
            decisions_by_session[session_id] = 0

            for decision in decisions:
                if not isinstance(decision, dict):
                    continue
                key = decision.get("key")
                if not isinstance(key, str) or not key:
                    continue
                row = {
                    "session_id": session_id,
                    "key": key,
                    "value": decision.get("value"),
                    "source": decision.get("source"),
                    "created_at": decision.get("created_at"),
                    "ttl_seconds": decision.get("ttl_seconds"),
                    "expires_at": decision.get("expires_at"),
                }
                decision_rows.append(row)
                decisions_by_session[session_id] += 1

    decisions_total = len(decision_rows)
    latest_by_key: dict[str, dict[str, Any]] = {}
    for row in sorted(decision_rows, key=_decision_key):
        latest_by_key[str(row.get("key"))] = row

    shared_decisions = sorted(latest_by_key.values(), key=lambda x: str(x.get("key") or ""))

    payload = {
        "version": "v1",
        "generated_at": now_iso,
        "workspace_root": str(workspace_root),
        "sessions_scanned": scanned_sessions,
        "sessions_loaded": loaded_sessions,
        "sessions_skipped": skipped_sessions,
        "decisions_total": decisions_total,
        "shared_keys_total": len(shared_decisions),
        "decisions_by_session": {k: int(v) for k, v in sorted(decisions_by_session.items())},
        "shared_decisions": shared_decisions,
        "notes": ["PROGRAM_LED=true", "SESSION_SCOPED=true"],
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "report_path": _rel_to_workspace(out_path, workspace_root),
        "shared_keys_total": len(shared_decisions),
        "sessions_loaded": loaded_sessions,
    }
