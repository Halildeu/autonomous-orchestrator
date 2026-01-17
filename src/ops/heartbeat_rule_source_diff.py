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


def _resolve_reports_path(workspace_root: Path, path_arg: str) -> Path | None:
    raw = Path(str(path_arg or "").strip())
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


def run_heartbeat_rule_source_diff(
    *,
    workspace_root: Path,
    pinpoint_path: Path | str,
    selection_path: Path | str,
    out_path: Path | str,
    now_iso: str | None = None,
) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}
    pinpoint_resolved = _resolve_reports_path(workspace_root, str(pinpoint_path))
    selection_resolved = _resolve_reports_path(workspace_root, str(selection_path))
    if pinpoint_resolved is None or selection_resolved is None:
        return {"status": "FAIL", "error_code": "INPUT_PATH_INVALID"}
    if not pinpoint_resolved.exists() or not selection_resolved.exists():
        return {"status": "FAIL", "error_code": "INPUT_MISSING"}

    pinpoint = _load_json(pinpoint_resolved)
    selection = _load_json(selection_resolved)
    if not isinstance(pinpoint, dict) or not isinstance(selection, dict):
        return {"status": "FAIL", "error_code": "INPUT_INVALID"}

    read_path = pinpoint.get("eval_runner_read_path")
    read_key = pinpoint.get("eval_runner_read_key")
    declared_path = pinpoint.get("declared_rule_path")
    declared_key = pinpoint.get("declared_rule_key")
    sel_path = selection.get("selected_input_file")
    sel_key = selection.get("selected_timestamp_key")
    if not isinstance(read_path, str) or not read_path.strip():
        return {"status": "FAIL", "error_code": "PINPOINT_READ_PATH_MISSING"}
    if not isinstance(read_key, str) or not read_key.strip():
        return {"status": "FAIL", "error_code": "PINPOINT_READ_KEY_MISSING"}
    if not isinstance(sel_path, str) or not sel_path.strip():
        return {"status": "FAIL", "error_code": "SELECTION_PATH_MISSING"}
    if not isinstance(sel_key, str) or not sel_key.strip():
        return {"status": "FAIL", "error_code": "SELECTION_KEY_MISSING"}

    declared_path = declared_path.strip() if isinstance(declared_path, str) and declared_path.strip() else None
    declared_key = declared_key.strip() if isinstance(declared_key, str) and declared_key.strip() else None
    declared_mismatch = None
    if declared_path and declared_key:
        declared_mismatch = {
            "path": declared_path != sel_path.strip(),
            "key": declared_key != sel_key.strip(),
        }

    payload = {
        "version": "v0.3",
        "generated_at": now_iso or _now_iso(),
        "workspace_root": str(workspace_root),
        "eval_runner_read": {"path": read_path.strip(), "key": read_key.strip()},
        "declared_rule": {"path": declared_path, "key": declared_key},
        "selection_target": {"path": sel_path.strip(), "key": sel_key.strip()},
        "mismatch": {
            "path": read_path.strip() != sel_path.strip(),
            "key": read_key.strip() != sel_key.strip(),
        },
        "declared_mismatch": declared_mismatch,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "READ_ONLY=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)
    return {"status": "OK", "report_path": rel}


def cmd_heartbeat_rule_source_diff(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    pinpoint_arg = str(args.pinpoint or ".cache/reports/eval_runner_heartbeat_pinpoint.v1.json")
    selection_arg = str(args.selection or ".cache/reports/eval_runner_heartbeat_exact_selection.v1.json")
    out_arg = str(args.out or ".cache/reports/heartbeat_rule_source_diff.v0.2.json")
    result = run_heartbeat_rule_source_diff(
        workspace_root=ws,
        pinpoint_path=pinpoint_arg,
        selection_path=selection_arg,
        out_path=out_arg,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_heartbeat_rule_source_diff_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "heartbeat-rule-source-diff",
        help="Compare eval_runner read path/key vs selection target (read-only).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument(
        "--pinpoint",
        default=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        help="Pinpoint JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--selection",
        default=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        help="Selection JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--out",
        default=".cache/reports/heartbeat_rule_source_diff.v0.2.json",
        help="Output JSON path under workspace .cache/reports.",
    )
    ap.set_defaults(func=cmd_heartbeat_rule_source_diff)
