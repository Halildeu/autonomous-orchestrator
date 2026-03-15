from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, resolve_workspace_root_arg, warn


def _ws(args: argparse.Namespace) -> Path | None:
    root = repo_root()
    raw = str(getattr(args, "workspace_root", "") or "").strip()
    if not raw:
        raw = "."
    return resolve_workspace_root_arg(root, raw, prefer_customer_workspace=True)


def _chat_mode(args: argparse.Namespace) -> bool:
    return str(getattr(args, "chat", "false")).strip().lower() in {"true", "1", "yes"}


def cmd_agent_claim(args: argparse.Namespace) -> int:
    ws = _ws(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2

    from src.ops.work_item_claims import acquire_claim

    result = acquire_claim(
        workspace_root=ws,
        work_item_id=str(args.work_item_id),
        owner_tag=str(args.agent_tag),
        agent_tag=str(args.agent_tag),
        owner_session=str(getattr(args, "session_id", "") or ""),
        ttl_seconds=int(args.ttl_seconds),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, default=str))
    return 0 if result.get("status") in {"ACQUIRED", "RENEWED"} else 1


def cmd_agent_release(args: argparse.Namespace) -> int:
    ws = _ws(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2

    from src.ops.work_item_claims import acquire_claim, release_claim

    transfer_to = str(getattr(args, "transfer_to", "") or "").strip()

    result = release_claim(
        workspace_root=ws,
        work_item_id=str(args.work_item_id),
        agent_tag=str(args.agent_tag) if args.agent_tag else None,
        force=bool(getattr(args, "force", False)),
    )

    if transfer_to and result.get("status") in {"RELEASED", "RELEASED_FORCED"}:
        acquire_result = acquire_claim(
            workspace_root=ws,
            work_item_id=str(args.work_item_id),
            owner_tag=transfer_to,
            agent_tag=transfer_to,
            ttl_seconds=int(args.ttl_seconds),
        )
        result["transfer"] = acquire_result

    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, default=str))
    return 0 if result.get("status") in {"RELEASED", "RELEASED_FORCED", "NOOP"} else 1


def cmd_agent_status(args: argparse.Namespace) -> int:
    ws = _ws(args)
    if ws is None:
        warn("FAIL error=WORKSPACE_NOT_FOUND")
        return 2

    from src.ops.work_item_claims import load_claims

    now = datetime.now(timezone.utc)
    all_claims = load_claims(ws)
    active: list[dict[str, Any]] = []
    for c in all_claims:
        if not isinstance(c, dict):
            continue
        exp_str = str(c.get("expires_at") or "")
        if exp_str:
            try:
                raw = exp_str
                if raw.endswith("Z"):
                    raw = raw[:-1] + "+00:00"
                exp = datetime.fromisoformat(raw)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now >= exp:
                    continue
            except Exception:
                continue
        active.append(c)

    agent_filter = str(getattr(args, "agent_tag", "") or "").strip()
    if agent_filter:
        active = [c for c in active if str(c.get("agent_tag") or "") == agent_filter]

    by_agent: dict[str, int] = {}
    for c in active:
        tag = str(c.get("agent_tag") or "unknown")
        by_agent[tag] = by_agent.get(tag, 0) + 1

    status = "IDLE"
    if active:
        status = "OK"
    if len(by_agent) > 1:
        # Multiple agents have active claims — potential coordination needed
        pass

    report: dict[str, Any] = {
        "version": "v1",
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "workspace_root": str(ws),
        "claims": active,
        "summary": {
            "total_active": len(active),
            "by_agent": dict(sorted(by_agent.items())),
            "conflicts": [],
        },
        "status": status,
    }

    if _chat_mode(args):
        lines = [f"RESULT status={status} active_claims={len(active)}"]
        for tag, count in sorted(by_agent.items()):
            lines.append(f"  agent={tag} claims={count}")
        for c in active:
            lines.append(f"  item={c.get('work_item_id')} agent={c.get('agent_tag')} expires={c.get('expires_at')}")
        print("\n".join(lines))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, default=str))

    return 0


def register_agent_handoff_subcommands(
    parent: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    # agent-claim
    ap_claim = parent.add_parser("agent-claim", help="Acquire a work-item claim for an agent.")
    ap_claim.add_argument("--workspace-root", default=".")
    ap_claim.add_argument("--work-item-id", required=True, help="Work item identifier")
    ap_claim.add_argument("--agent-tag", required=True, help="Agent name (codex, claude, antigravity)")
    ap_claim.add_argument("--session-id", default="", help="Session identifier")
    ap_claim.add_argument("--ttl-seconds", type=int, default=3600, help="Claim TTL in seconds")
    ap_claim.add_argument("--chat", default="false")
    ap_claim.set_defaults(func=cmd_agent_claim)

    # agent-release
    ap_release = parent.add_parser("agent-release", help="Release a work-item claim, optionally transfer.")
    ap_release.add_argument("--workspace-root", default=".")
    ap_release.add_argument("--work-item-id", required=True, help="Work item identifier")
    ap_release.add_argument("--agent-tag", default="", help="Agent name to verify ownership")
    ap_release.add_argument("--transfer-to", default="", help="Agent name to transfer claim to")
    ap_release.add_argument("--ttl-seconds", type=int, default=3600, help="TTL for transferred claim")
    ap_release.add_argument("--force", action="store_true", help="Force release ignoring ownership")
    ap_release.add_argument("--chat", default="false")
    ap_release.set_defaults(func=cmd_agent_release)

    # agent-status
    ap_status = parent.add_parser("agent-status", help="Show active agent claims.")
    ap_status.add_argument("--workspace-root", default=".")
    ap_status.add_argument("--agent-tag", default="", help="Filter by agent name")
    ap_status.add_argument("--chat", default="false")
    ap_status.set_defaults(func=cmd_agent_status)
