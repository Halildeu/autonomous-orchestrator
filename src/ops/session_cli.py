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
    inherit_parent_decisions,
    is_expired,
    link_to_parent,
    load_context,
    mark_compaction,
    new_context,
    prune_expired_decisions,
    renew_context,
    save_context_atomic,
    upsert_provider_state,
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


def cmd_session_provider_state_set(args: argparse.Namespace) -> int:
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
        upsert_provider_state(
            ctx,
            provider=str(args.provider or "").strip(),
            wire_api=str(args.wire_api or "").strip() or "responses",
            conversation_id=str(args.conversation_id or "").strip(),
            last_response_id=str(args.last_response_id or "").strip(),
            summary_ref=str(args.summary_ref or "").strip(),
        )
        save_context_atomic(ctx_path, ctx)
    except SessionContextError as e:
        _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
        return 2

    _print_json({"status": "OK", "session_id": session_id, "path": str(ctx_path.relative_to(workspace_root))})
    return 0


def cmd_session_compaction_mark(args: argparse.Namespace) -> int:
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
        approx_input_tokens = int(args.approx_input_tokens or 0)
        ctx = load_context(ctx_path)
        mark_compaction(
            ctx,
            summary_ref=str(args.summary_ref or "").strip(),
            trigger=str(args.trigger or "").strip() or "manual",
            source=str(args.source or "").strip() or "local",
            approx_input_tokens=approx_input_tokens,
        )
        save_context_atomic(ctx_path, ctx)
    except SessionContextError as e:
        _print_json({"status": "FAIL", "error_code": e.error_code, "message": e.message})
        return 2
    except ValueError:
        _print_json({"status": "FAIL", "error_code": "INVALID_ARGS", "message": "approx-input-tokens must be int"})
        return 2

    _print_json({"status": "OK", "session_id": session_id, "path": str(ctx_path.relative_to(workspace_root))})
    return 0


def cmd_session_link_parent(args: argparse.Namespace) -> int:
    """Link a child session to its parent (orchestrator → managed repo)."""
    ws = _resolve_workspace_root(str(args.workspace_root))
    parent_ws = str(args.parent_workspace).strip()
    session_id = str(args.session_id).strip() or "default"

    if not parent_ws:
        print(json.dumps({"status": "FAIL", "error_code": "MISSING_PARENT_WORKSPACE"}, sort_keys=True))
        return 2

    sp = SessionPaths(workspace_root=ws, session_id=session_id)
    if not sp.context_path.exists():
        try:
            ctx = new_context(session_id, str(ws), 604800)
            save_context_atomic(sp.context_path, ctx)
        except SessionContextError as e:
            print(json.dumps({"status": "FAIL", "error_code": e.error_code}, sort_keys=True))
            return 2

    try:
        ctx = load_context(sp.context_path)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if is_expired(ctx, now_iso):
            ctx = renew_context(ctx, 604800)
        ctx = link_to_parent(ctx, parent_workspace_root=parent_ws, parent_session_id=session_id)

        # Inherit parent decisions if parent exists
        parent_sp = SessionPaths(workspace_root=Path(parent_ws), session_id=session_id)
        inherited = 0
        if parent_sp.context_path.exists():
            try:
                parent_ctx = load_context(parent_sp.context_path)
                before = len(ctx.get("ephemeral_decisions", []))
                ctx = inherit_parent_decisions(ctx, parent_context=parent_ctx)
                inherited = len(ctx.get("ephemeral_decisions", [])) - before
            except SessionContextError:
                pass

        save_context_atomic(sp.context_path, ctx)
        print(json.dumps({
            "status": "OK",
            "session_id": session_id,
            "parent_workspace": parent_ws,
            "inherited_decisions": inherited,
        }, sort_keys=True))
        return 0
    except SessionContextError as e:
        print(json.dumps({"status": "FAIL", "error_code": e.error_code}, sort_keys=True))
        return 2


def cmd_session_sync(args: argparse.Namespace) -> int:
    """Sync decisions between parent and child sessions."""
    ws = _resolve_workspace_root(str(args.workspace_root))
    session_id = str(args.session_id).strip() or "default"
    direction = str(args.direction).strip().lower()

    sp = SessionPaths(workspace_root=ws, session_id=session_id)
    if not sp.context_path.exists():
        print(json.dumps({"status": "FAIL", "error_code": "SESSION_NOT_FOUND"}, sort_keys=True))
        return 2

    try:
        ctx = load_context(sp.context_path)
    except SessionContextError as e:
        print(json.dumps({"status": "FAIL", "error_code": e.error_code}, sort_keys=True))
        return 2

    parent_ref = ctx.get("parent_session_ref")
    if not isinstance(parent_ref, dict) or not parent_ref.get("workspace_root"):
        print(json.dumps({"status": "FAIL", "error_code": "NO_PARENT_LINKED"}, sort_keys=True))
        return 2

    parent_ws = Path(str(parent_ref["workspace_root"]))
    parent_session_id = str(parent_ref.get("session_id") or "default")
    parent_sp = SessionPaths(workspace_root=parent_ws, session_id=parent_session_id)

    if not parent_sp.context_path.exists():
        print(json.dumps({"status": "FAIL", "error_code": "PARENT_SESSION_NOT_FOUND"}, sort_keys=True))
        return 2

    try:
        parent_ctx = load_context(parent_sp.context_path)
    except SessionContextError as e:
        print(json.dumps({"status": "FAIL", "error_code": f"PARENT_{e.error_code}"}, sort_keys=True))
        return 2

    inherited = 0
    if direction in ("pull", "both"):
        before = len(ctx.get("ephemeral_decisions", []))
        ctx = inherit_parent_decisions(ctx, parent_context=parent_ctx)
        inherited = len(ctx.get("ephemeral_decisions", [])) - before
        save_context_atomic(sp.context_path, ctx)

    pushed = 0
    if direction in ("push", "both"):
        before = len(parent_ctx.get("ephemeral_decisions", []))
        parent_ctx = inherit_parent_decisions(parent_ctx, parent_context=ctx, overwrite_existing=False)
        pushed = len(parent_ctx.get("ephemeral_decisions", [])) - before
        if pushed > 0:
            save_context_atomic(parent_sp.context_path, parent_ctx)

    print(json.dumps({
        "status": "OK",
        "direction": direction,
        "inherited_from_parent": inherited,
        "pushed_to_parent": pushed,
    }, sort_keys=True))
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

    ap_provider = subparsers.add_parser(
        "session-provider-state-set", help="Persist provider conversation metadata in a session context."
    )
    ap_provider.add_argument("--workspace-root", required=True)
    ap_provider.add_argument("--session-id", default="default")
    ap_provider.add_argument("--provider", required=True)
    ap_provider.add_argument("--wire-api", default="responses")
    ap_provider.add_argument("--conversation-id", default="")
    ap_provider.add_argument("--last-response-id", default="")
    ap_provider.add_argument("--summary-ref", default="")
    ap_provider.set_defaults(func=cmd_session_provider_state_set)

    ap_compact = subparsers.add_parser("session-compaction-mark", help="Record a compaction summary reference.")
    ap_compact.add_argument("--workspace-root", required=True)
    ap_compact.add_argument("--session-id", default="default")
    ap_compact.add_argument("--summary-ref", required=True)
    ap_compact.add_argument("--trigger", default="manual")
    ap_compact.add_argument("--source", default="local")
    ap_compact.add_argument("--approx-input-tokens", default="0")
    ap_compact.set_defaults(func=cmd_session_compaction_mark)

    ap_link = subparsers.add_parser("session-link-parent", help="Link child session to parent (orchestrator → managed repo).")
    ap_link.add_argument("--workspace-root", required=True)
    ap_link.add_argument("--parent-workspace", required=True, help="Parent (orchestrator) workspace root path.")
    ap_link.add_argument("--session-id", default="default")
    ap_link.set_defaults(func=cmd_session_link_parent)

    ap_sync = subparsers.add_parser("session-sync", help="Sync decisions between parent and child sessions.")
    ap_sync.add_argument("--workspace-root", required=True)
    ap_sync.add_argument("--session-id", default="default")
    ap_sync.add_argument("--direction", default="pull", choices=["push", "pull", "both"], help="Sync direction: pull (from parent), push (to parent), both.")
    ap_sync.set_defaults(func=cmd_session_sync)
