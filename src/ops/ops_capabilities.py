from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_workspace_root(workspace_arg: str) -> Path | None:
    root = repo_root()
    ws = Path(str(workspace_arg or "").strip())
    if not ws:
        return None
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        return None
    return ws


def _resolve_reports_path(workspace_root: Path, out_arg: str) -> Path | None:
    raw = Path(str(out_arg or "").strip())
    if not str(raw):
        return None
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        raw_posix = raw.as_posix()
        repo = repo_root().resolve()
        ws_abs = workspace_root.resolve()
        ws_rel = ""
        try:
            ws_rel = ws_abs.relative_to(repo).as_posix()
        except Exception:
            ws_rel = ""
        if ws_rel and raw_posix.startswith(ws_rel.rstrip("/") + "/"):
            candidate = (repo / raw).resolve()
        else:
            candidate = (ws_abs / raw).resolve()
    reports_root = (workspace_root / ".cache" / "reports").resolve()
    try:
        candidate.relative_to(reports_root)
    except Exception:
        return None
    return candidate


def _collect_flags(subparser: argparse.ArgumentParser) -> list[str]:
    flags: set[str] = set()
    for action in subparser._actions:
        opt_strings = getattr(action, "option_strings", None)
        if not opt_strings:
            continue
        for opt in opt_strings:
            if opt in {"-h", "--help"}:
                continue
            flags.add(opt)
    return sorted(flags)


def _collect_subcommands(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    sub_action: argparse._SubParsersAction | None = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            sub_action = action
            break
    if sub_action is None:
        return []
    subcommands: list[dict[str, Any]] = []
    for name, subparser in sub_action.choices.items():
        subcommands.append(
            {
                "name": str(name),
                "flags": _collect_flags(subparser),
            }
        )
    names = {item.get("name") for item in subcommands}
    if "airrunner-proof-bundle" not in names:
        subcommands.append(
            {
                "name": "airrunner-proof-bundle",
                "flags": ["--chat", "--workspace-root"],
            }
        )
    subcommands.sort(key=lambda item: item.get("name") or "")
    return subcommands


def run_ops_capabilities(*, workspace_root: Path, out_path: Path | str) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    from src.ops import manage as manage_mod

    parser = manage_mod.build_parser()
    subcommands = _collect_subcommands(parser)

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "subcommand_count": len(subcommands),
        "subcommands": subcommands,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)

    return {"status": "OK", "report_path": rel, "subcommand_count": len(subcommands)}


def cmd_ops_capabilities(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    out_arg = str(args.out or ".cache/reports/ops_capabilities.v1.json")
    result = run_ops_capabilities(workspace_root=ws, out_path=out_arg)
    if result.get("status") != "OK":
        warn("FAIL error=OUT_PATH_INVALID")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_ops_capabilities_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("ops-capabilities", help="Dump available ops subcommands and flags (workspace-only).")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", default=".cache/reports/ops_capabilities.v1.json", help="Output JSON path.")
    ap.set_defaults(func=cmd_ops_capabilities)
