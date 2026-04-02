from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.ops.commands.common import repo_root, warn
from src.ops.trace_meta import build_run_id, build_trace_meta

from src.shared.utils import write_json_atomic

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


def _normalize_evidence(items: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for item in items or []:
        value = str(item or "").strip()
        if value:
            out.append(value)
    return sorted(set(out))


def run_closeout_write(
    *,
    workspace_root: Path,
    out_path: Path | str,
    title: str,
    evidence_paths: Iterable[str] | None,
    actor_role: str | None = None,
    actor: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    handoff_from: str | None = None,
) -> dict[str, Any]:
    title = str(title or "").strip()
    if not title:
        return {"status": "FAIL", "error_code": "TITLE_REQUIRED"}

    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    evidence = _normalize_evidence(evidence_paths)
    generated_at = _now_iso()
    inputs = {"title": title, "out_path": str(out_resolved), "evidence_paths": evidence}
    run_id = build_run_id(workspace_root=workspace_root, op_name="closeout-write", inputs=inputs)
    work_item_id = run_id

    trace_meta = build_trace_meta(
        work_item_id=work_item_id,
        work_item_kind="CLOSEOUT",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=evidence,
        workspace_root=str(workspace_root),
    )
    if str(actor_role or "").strip():
        trace_meta["actor_role"] = str(actor_role).strip()
    if str(actor or "").strip():
        trace_meta["actor"] = str(actor).strip()
    if str(provider or "").strip():
        trace_meta["provider_used"] = str(provider).strip()
    if str(model or "").strip():
        trace_meta["model_used"] = str(model).strip()
    if str(handoff_from or "").strip():
        trace_meta["handoff_from"] = str(handoff_from).strip()

    try:
        out_rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        out_rel = str(out_resolved)

    payload = {
        "version": "v1",
        "generated_at": generated_at,
        "title": title,
        "workspace_root": str(workspace_root),
        "report_path": out_rel,
        "evidence_paths": evidence,
        "trace_meta": trace_meta,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
    }
    if str(actor_role or "").strip():
        payload["actor_role"] = str(actor_role).strip()
    if str(actor or "").strip():
        payload["actor"] = str(actor).strip()
    if str(provider or "").strip():
        payload["provider"] = str(provider).strip()
    if str(model or "").strip():
        payload["model"] = str(model).strip()
    if str(handoff_from or "").strip():
        payload["handoff_from"] = str(handoff_from).strip()

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_resolved, payload)

    return {"status": "OK", "report_path": out_rel, "trace_meta": trace_meta}


def cmd_closeout_write(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    out_arg = str(args.out or "")
    title = str(args.title or "")
    evidence = list(getattr(args, "evidence", []) or [])
    result = run_closeout_write(
        workspace_root=ws,
        out_path=out_arg,
        title=title,
        evidence_paths=evidence,
        actor_role=str(getattr(args, "actor_role", "") or ""),
        actor=str(getattr(args, "actor", "") or ""),
        provider=str(getattr(args, "provider", "") or ""),
        model=str(getattr(args, "model", "") or ""),
        handoff_from=str(getattr(args, "handoff_from", "") or ""),
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_closeout_write_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("closeout-write", help="Write a workspace-only closeout JSON under .cache/reports.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", required=True, help="Output JSON path (must be under workspace .cache/reports).")
    ap.add_argument("--title", required=True, help="Closeout title.")
    ap.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Evidence path (repeatable).",
    )
    ap.add_argument("--actor-role", default="", help="Optional actor role.")
    ap.add_argument("--actor", default="", help="Optional actor id.")
    ap.add_argument("--provider", default="", help="Optional provider name.")
    ap.add_argument("--model", default="", help="Optional model name.")
    ap.add_argument("--handoff-from", default="", help="Optional originating handoff id.")
    ap.set_defaults(func=cmd_closeout_write)
