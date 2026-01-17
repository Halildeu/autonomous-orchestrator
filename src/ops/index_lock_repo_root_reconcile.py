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


def _find_repo_root(start: Path) -> Path | None:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return None


def _backup_dir(workspace_root: Path, ts: str) -> Path:
    safe_ts = ts.replace(":", "").replace("-", "")
    return workspace_root / ".cache" / "reports" / "index_lock_backup" / safe_ts


def run_index_lock_repo_root_reconcile(
    *,
    workspace_root: Path,
    out_path: Path | str,
    repo_root_override: Path | None = None,
) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    repo = repo_root_override or _find_repo_root(repo_root())
    if repo is None:
        return {"status": "FAIL", "error_code": "REPO_ROOT_NOT_FOUND"}

    expected_lock = (repo / ".git" / "index.lock").resolve()
    if expected_lock != expected_lock.resolve():
        return {"status": "FAIL", "error_code": "LOCK_PATH_INVALID"}

    lock_exists = expected_lock.exists()
    moved_path: str | None = None
    backup_dir: Path | None = None
    status = "NOOP"
    error_code: str | None = None

    if lock_exists:
        ts = _now_iso()
        backup_dir = _backup_dir(workspace_root, ts)
        if backup_dir.exists():
            return {"status": "FAIL", "error_code": "BACKUP_DIR_EXISTS"}
        backup_dir.mkdir(parents=True, exist_ok=False)
        target = (backup_dir / "index.lock").resolve()
        try:
            expected_lock.replace(target)
            moved_path = str(target)
            status = "OK"
        except Exception:
            status = "FAIL"
            error_code = "MOVE_FAILED"

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "repo_root": str(repo),
        "lock_path": str(expected_lock),
        "lock_exists_before": lock_exists,
        "status": status,
        "error_code": error_code,
        "backup_dir": str(backup_dir) if backup_dir else None,
        "moved_path": moved_path,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "FAIL_CLOSED=true"],
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
    return {"status": status, "report_path": rel, "lock_exists": lock_exists, "error_code": error_code}


def cmd_index_lock_repo_root_reconcile(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    out_arg = str(args.out or ".cache/reports/index_lock_repo_root_reconcile.v0.1.json")
    result = run_index_lock_repo_root_reconcile(workspace_root=ws, out_path=out_arg)
    if result.get("status") not in ("OK", "NOOP"):
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_index_lock_repo_root_reconcile_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "index-lock-repo-root-reconcile",
        help="Safely move repo-root .git/index.lock to workspace backup (no delete).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument(
        "--out",
        default=".cache/reports/index_lock_repo_root_reconcile.v0.1.json",
        help="Output JSON path under workspace .cache/reports.",
    )
    ap.set_defaults(func=cmd_index_lock_repo_root_reconcile)
