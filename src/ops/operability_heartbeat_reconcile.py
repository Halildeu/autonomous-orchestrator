from __future__ import annotations

import argparse
import json
import os
import re
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


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _load_selection(report_path: Path) -> tuple[str | None, str | None]:
    data = _load_json(report_path)
    if not isinstance(data, dict):
        return None, None
    file_key = data.get("selected_input_file") or data.get("selected_input_path")
    ts_key = data.get("selected_timestamp_key") or data.get("selected_key")
    if not isinstance(file_key, str) or not file_key.strip():
        return None, None
    if not isinstance(ts_key, str) or not ts_key.strip():
        return None, None
    return file_key.strip(), ts_key.strip()


def _resolve_candidate_path(workspace_root: Path, rel_path: str) -> Path | None:
    raw = Path(rel_path)
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (workspace_root / raw).resolve()
    try:
        candidate.relative_to(workspace_root.resolve())
    except Exception:
        return None
    return candidate


def _candidate_from_find_report(workspace_root: Path, report_path: Path) -> tuple[str | None, str | None]:
    if not report_path.exists():
        return None, None
    data = _load_json(report_path)
    if not isinstance(data, dict):
        return None, None
    matches = data.get("matches")
    if not isinstance(matches, list) or not matches:
        return None, None
    first = sorted({str(m) for m in matches if isinstance(m, str) and m.strip()})[0]
    resolved = _resolve_candidate_path(workspace_root, first)
    return (first, str(resolved)) if resolved is not None else (None, None)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _resolve_selected_input(workspace_root: Path, selected_input: str) -> tuple[Path | None, str | None]:
    resolved = _resolve_candidate_path(workspace_root, selected_input.strip())
    if resolved is None:
        return None, None
    try:
        rel = resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = resolved.as_posix()
    if not rel.startswith(".cache/"):
        return None, None
    return resolved, rel


def run_operability_heartbeat_reconcile(
    *,
    workspace_root: Path,
    out_path: Path | str,
    find_report: Path | None = None,
) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    selection_report = (
        workspace_root / ".cache" / "reports" / "eval_runner_heartbeat_exact_selection.v1.json"
    )
    selected_file, selected_key = _load_selection(selection_report)
    if selected_file is None or selected_key is None:
        return {"status": "FAIL", "error_code": "SELECTION_MISSING"}

    candidate, candidate_rel = _resolve_selected_input(workspace_root, selected_file)
    if candidate is None or candidate_rel is None:
        return {"status": "FAIL", "error_code": "SELECTION_PATH_INVALID"}

    now = _now_iso()
    created_new = False
    if candidate.exists():
        heartbeat = _load_json(candidate)
        if not isinstance(heartbeat, dict):
            return {"status": "FAIL", "error_code": "HEARTBEAT_INVALID_OR_MISSING"}
    else:
        heartbeat = {"version": "v1"}
        created_new = True

    previous_value = heartbeat.get(selected_key)
    previous_ended_at = heartbeat.get("ended_at")
    previous_last_tick_at = heartbeat.get("last_tick_at")
    heartbeat[selected_key] = now
    heartbeat["ended_at"] = now
    heartbeat["last_tick_at"] = now

    _atomic_write_json(candidate, heartbeat)

    try:
        rel = candidate.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(candidate)

    payload = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(workspace_root),
        "heartbeat_path": rel,
        "found_via": "selection_report",
        "selection_report_path": str(selection_report),
        "selected_input_file": selected_file,
        "selected_timestamp_key": selected_key,
        "created_new": created_new,
        "previous_value": previous_value,
        "updated_value": now,
        "previous_ended_at": previous_ended_at,
        "updated_ended_at": now,
        "previous_last_tick_at": previous_last_tick_at,
        "updated_last_tick_at": now,
        "find_report_path": str(find_report) if find_report else "",
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    try:
        out_rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        out_rel = str(out_resolved)

    return {"status": "OK", "report_path": out_rel, "heartbeat_path": rel}


def cmd_operability_heartbeat_reconcile(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    out_arg = str(args.out or ".cache/reports/heartbeat_reconcile.v0.2.json")
    find_arg = str(args.find_report or "")
    find_report = Path(find_arg) if find_arg else None
    if find_report is not None and not find_report.is_absolute():
        find_report = (repo_root() / find_report).resolve()
    result = run_operability_heartbeat_reconcile(workspace_root=ws, out_path=out_arg, find_report=find_report)
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_operability_heartbeat_reconcile_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("operability-heartbeat-reconcile", help="Refresh airunner heartbeat timestamp (local).")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", default=".cache/reports/heartbeat_reconcile.v0.2.json", help="Output JSON path.")
    ap.add_argument(
        "--find-report",
        default="",
        help="Optional workspace-find report path for heartbeat hints.",
    )
    ap.set_defaults(func=cmd_operability_heartbeat_reconcile)
