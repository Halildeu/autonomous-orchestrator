from __future__ import annotations

import argparse
import json
import os
import time
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


def _walk_cache(cache_root: Path, name_query: str, max_depth: int, max_files: int) -> list[Path]:
    matches: list[Path] = []
    scanned = 0
    query = name_query.lower()
    root_depth = len(cache_root.parts)
    for dirpath, dirnames, filenames in os.walk(cache_root):
        current_depth = len(Path(dirpath).parts) - root_depth
        if current_depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            scanned += 1
            if scanned > max_files:
                return matches
            if query in filename.lower():
                matches.append(Path(dirpath) / filename)
    return matches


def run_github_ops_index_lock_clear_local(
    *,
    workspace_root: Path,
    out_path: Path | str,
    mode: str = "stale_clear",
    max_age_seconds: int = 3600,
    max_depth: int = 6,
    max_files: int = 2000,
) -> dict[str, Any]:
    if mode not in {"stale_clear", "force"}:
        return {"status": "FAIL", "error_code": "INVALID_MODE"}
    if max_age_seconds < 0:
        return {"status": "FAIL", "error_code": "INVALID_MAX_AGE"}

    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    cache_root = (workspace_root / ".cache").resolve()
    if not cache_root.exists() or not cache_root.is_dir():
        return {"status": "FAIL", "error_code": "CACHE_ROOT_MISSING"}

    candidates = _walk_cache(cache_root, "index_lock", max_depth=max_depth, max_files=max_files)
    candidates = sorted({p.resolve() for p in candidates})

    now_ts = time.time()
    cleared: list[str] = []
    retained: list[str] = []
    errors: list[dict[str, Any]] = []

    for path in candidates:
        try:
            age_seconds = int(now_ts - path.stat().st_mtime)
        except Exception as exc:
            errors.append({"path": str(path), "error": f"STAT_FAILED:{exc.__class__.__name__}"})
            continue
        should_clear = mode == "force" or age_seconds > int(max_age_seconds)
        if should_clear:
            try:
                path.unlink()
                cleared.append(str(path))
            except Exception as exc:
                errors.append({"path": str(path), "error": f"UNLINK_FAILED:{exc.__class__.__name__}"})
        else:
            retained.append(str(path))

    try:
        ws_root = workspace_root.resolve()
        cleared = [str(Path(p).resolve().relative_to(ws_root).as_posix()) for p in cleared]
        retained = [str(Path(p).resolve().relative_to(ws_root).as_posix()) for p in retained]
        candidates_rel = [str(p.relative_to(ws_root).as_posix()) for p in candidates]
    except Exception:
        candidates_rel = [str(p) for p in candidates]

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "mode": mode,
        "max_age_seconds": int(max_age_seconds),
        "matched_count": len(candidates_rel),
        "matched_paths": sorted(candidates_rel),
        "cleared_count": len(cleared),
        "cleared_paths": sorted(cleared),
        "retained_paths": sorted(retained),
        "errors": errors,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)
    return {"status": "OK", "report_path": rel, "cleared_count": len(cleared), "matched_count": len(candidates_rel)}


def cmd_github_ops_index_lock_clear_local(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    out_arg = str(args.out or ".cache/reports/index_lock_clear_local.v0.2.json")
    mode = str(args.mode or "stale_clear")
    try:
        max_age = int(args.max_age_seconds)
    except Exception:
        warn("FAIL error=INVALID_MAX_AGE")
        return 2
    result = run_github_ops_index_lock_clear_local(
        workspace_root=ws,
        out_path=out_arg,
        mode=mode,
        max_age_seconds=max_age,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_github_ops_index_lock_clear_local_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "github-ops-index-lock-clear-local",
        help="Clear workspace-local github ops index_lock files (stale-safe).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", default=".cache/reports/index_lock_clear_local.v0.2.json", help="Output JSON path.")
    ap.add_argument("--mode", default="stale_clear", help="stale_clear|force (default: stale_clear).")
    ap.add_argument("--max-age-seconds", default="3600", help="Stale age threshold in seconds (default: 3600).")
    ap.set_defaults(func=cmd_github_ops_index_lock_clear_local)
