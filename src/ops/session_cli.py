from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.session.context_store import (
    SessionContextError,
    SessionPaths,
    load_context,
    new_context,
    prune_expired_decisions,
    save_context_atomic,
    upsert_decision,
)


def _repo_root() -> Path:
    # src/ops/session_cli.py -> ops -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _resolve_workspace_root(raw: str) -> Path:
    root = _repo_root()
    p = Path(str(raw))
    return (root / p).resolve() if not p.is_absolute() else p.resolve()


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cmd_session_init(args: argparse.Namespace) -> int:
    workspace_root = _resolve_workspace_root(str(args.workspace_root))
    session_id = str(args.session_id).strip()
    if not session_id:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "session_id is required"})
        return 2

    try:
        ttl_seconds = int(args.ttl_seconds)
    except Exception:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "ttl_seconds must be int"})
        return 2

    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    ctx_path = sp.context_path

    if ctx_path.exists():
        try:
            ctx = load_context(ctx_path)
        except SessionContextError as e:
            _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
            return 2
        hashes = ctx.get("hashes") if isinstance(ctx, dict) else None
        sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
        _print_json(
            {
                "status": "OK",
                "session_id": session_id,
                "path": str(ctx_path.relative_to(workspace_root)),
                "expires_at": ctx.get("expires_at"),
                "sha256": sha,
            }
        )
        return 0

    try:
        ctx = new_context(session_id=session_id, workspace_root=str(workspace_root), ttl_seconds=ttl_seconds)
        save_context_atomic(ctx_path, ctx)
        ctx2 = load_context(ctx_path)
    except SessionContextError as e:
        _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
        return 2

    hashes = ctx2.get("hashes") if isinstance(ctx2, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    _print_json(
        {
            "status": "OK",
            "session_id": session_id,
            "path": str(ctx_path.relative_to(workspace_root)),
            "expires_at": ctx2.get("expires_at"),
            "sha256": sha,
        }
    )
    return 0


def cmd_session_set(args: argparse.Namespace) -> int:
    workspace_root = _resolve_workspace_root(str(args.workspace_root))
    session_id = str(args.session_id).strip()
    if not session_id:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "session_id is required"})
        return 2
    key = str(args.key).strip()
    if not key:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "key is required"})
        return 2

    try:
        value = json.loads(str(args.value_json))
    except Exception:
        _print_json({"status": "FAIL", "error_code": "INVALID_VALUE_JSON", "message": "value-json must be valid JSON"})
        return 2
    decision_ttl_seconds = None
    if getattr(args, "decision_ttl_seconds", None) not in {None, ""}:
        try:
            decision_ttl_seconds = int(args.decision_ttl_seconds)
        except Exception:
            _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "decision-ttl-seconds must be int"})
            return 2

    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    ctx_path = sp.context_path
    if not ctx_path.exists():
        _print_json({"status": "FAIL", "error_code": "SESSION_NOT_FOUND", "message": "session context not found"})
        return 2

    try:
        ctx = load_context(ctx_path)
        prune_expired_decisions(ctx, _now_iso8601())
        upsert_decision(ctx, key=key, value=value, source="agent", decision_ttl_seconds=decision_ttl_seconds)
        save_context_atomic(ctx_path, ctx)
        ctx2 = load_context(ctx_path)
    except SessionContextError as e:
        _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
        return 2

    hashes = ctx2.get("hashes") if isinstance(ctx2, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    _print_json({"status": "OK", "session_id": session_id, "sha256": sha})
    return 0


def cmd_session_status(args: argparse.Namespace) -> int:
    workspace_root = _resolve_workspace_root(str(args.workspace_root))
    session_id = str(args.session_id).strip()
    if not session_id:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "session_id is required"})
        return 2

    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    ctx_path = sp.context_path
    if not ctx_path.exists():
        _print_json({"status": "FAIL", "error_code": "SESSION_NOT_FOUND", "message": "session context not found"})
        return 2

    try:
        ctx = load_context(ctx_path)
        before = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        prune_expired_decisions(ctx, _now_iso8601())
        after = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if before != after:
            save_context_atomic(ctx_path, ctx)
            ctx = load_context(ctx_path)
    except SessionContextError as e:
        _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
        return 2

    hashes = ctx.get("hashes") if isinstance(ctx, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    payload = {
        "status": "OK",
        "session_id": session_id,
        "path": str(ctx_path.relative_to(workspace_root)),
        "expires_at": ctx.get("expires_at"),
        "sha256": sha,
        "decisions_count": len(ctx.get("ephemeral_decisions") or []) if isinstance(ctx.get("ephemeral_decisions"), list) else 0,
    }

    chat = str(getattr(args, "chat", "false")).lower() == "true"
    if chat:
        print("PREVIEW:")
        print(f"- session_id={session_id}")
        print("RESULT:")
        print("- status=OK")
        print("EVIDENCE:")
        print(f"- {payload['path']}")
        print("ACTIONS:")
        print("- none")
        print("NEXT:")
        print("- Continue in natural language; the agent updates session context as needed.")
        _print_json(payload)
        return 0

    _print_json(payload)
    return 0


def register_session_subcommands(subparsers: argparse._SubParsersAction) -> None:
    ap_init = subparsers.add_parser("session-init", help="Create a session context if missing (workspace-scoped).")
    ap_init.add_argument("--workspace-root", required=True)
    ap_init.add_argument("--session-id", default="default")
    ap_init.add_argument("--ttl-seconds", default="86400")
    ap_init.set_defaults(func=cmd_session_init)

    ap_set = subparsers.add_parser("session-set", help="Upsert an ephemeral decision into a session context.")
    ap_set.add_argument("--workspace-root", required=True)
    ap_set.add_argument("--session-id", default="default")
    ap_set.add_argument("--key", required=True)
    ap_set.add_argument("--value-json", required=True)
    ap_set.add_argument("--decision-ttl-seconds", default="", help="Optional per-decision TTL seconds [60..604800].")
    ap_set.set_defaults(func=cmd_session_set)

    ap_stat = subparsers.add_parser("session-status", help="Show session context summary.")
    ap_stat.add_argument("--workspace-root", required=True)
    ap_stat.add_argument("--session-id", default="default")
    ap_stat.add_argument("--chat", default="false", help="true|false (optional)")
    ap_stat.set_defaults(func=cmd_session_status)
