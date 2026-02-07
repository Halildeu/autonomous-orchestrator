from __future__ import annotations

import argparse
import json
import os
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


def _parse_allowlist(raw: str | None) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return [".cache"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if parts else [".cache"]


def _resolve_allow_root(workspace_root: Path, rel: str) -> tuple[str, Path] | None:
    raw = Path(rel)
    if raw.is_absolute():
        return None
    if ".." in raw.parts:
        return None
    rel_posix = raw.as_posix()
    if rel_posix in {"", "."}:
        rel_posix = "."
    target = (workspace_root / rel_posix).resolve()
    try:
        target.relative_to(workspace_root.resolve())
    except Exception:
        return None
    return rel_posix, target


def _walk_matches(root: Path, name_query: str, max_depth: int, max_files: int) -> tuple[list[str], int, bool]:
    matches: list[str] = []
    scanned = 0
    truncated = False
    query = name_query.lower()
    root_depth = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = len(Path(dirpath).parts) - root_depth
        if current_depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            scanned += 1
            if scanned > max_files:
                truncated = True
                break
            if query in filename.lower():
                matches.append(str(Path(dirpath) / filename))
        if truncated:
            break
    return matches, scanned, truncated


def run_workspace_find(
    *,
    workspace_root: Path,
    name: str,
    out_path: Path | str,
    allowlist: list[str] | None = None,
    max_depth: int = 6,
    max_files: int = 2000,
) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        return {"status": "FAIL", "error_code": "NAME_REQUIRED"}
    if max_depth < 0 or max_files < 1:
        return {"status": "FAIL", "error_code": "INVALID_BOUNDS"}

    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    allow_raw = allowlist if allowlist is not None else _parse_allowlist(None)
    allow_roots: list[tuple[str, Path]] = []
    for entry in allow_raw:
        resolved = _resolve_allow_root(workspace_root, entry)
        if resolved is None:
            return {"status": "FAIL", "error_code": "ALLOWLIST_INVALID"}
        allow_roots.append(resolved)

    allow_roots.sort(key=lambda item: item[0])
    roots = [(rel, path) for rel, path in allow_roots if path.exists() and path.is_dir()]
    missing_roots = [rel for rel, path in allow_roots if not path.exists()]

    matches: list[str] = []
    scanned_total = 0
    truncated = False
    for _, root in roots:
        root_matches, scanned, truncated_local = _walk_matches(root, name, max_depth, max_files - scanned_total)
        scanned_total += scanned
        matches.extend(root_matches)
        if truncated_local:
            truncated = True
            break

    try:
        ws_root = workspace_root.resolve()
        matches = [str(Path(m).resolve().relative_to(ws_root).as_posix()) for m in matches]
    except Exception:
        matches = [str(Path(m)) for m in matches]

    matches = sorted(set(matches))

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "query": {"name": name, "case_insensitive": True},
        "allowlist": [rel for rel, _ in allow_roots],
        "missing_roots": missing_roots,
        "max_depth": max_depth,
        "max_files": max_files,
        "scanned_files": scanned_total,
        "matched_count": len(matches),
        "matches": matches,
        "truncated": truncated,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)

    return {"status": "OK", "report_path": rel, "matched_count": len(matches)}


def cmd_workspace_find(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    name = str(args.name or "")
    allow = _parse_allowlist(str(getattr(args, "allow", "") or ""))
    try:
        max_depth = int(args.max_depth)
        max_files = int(args.max_files)
    except Exception:
        warn("FAIL error=INVALID_BOUNDS")
        return 2

    out_arg = str(args.out or ".cache/reports/workspace_find.v1.json")
    result = run_workspace_find(
        workspace_root=ws,
        name=name,
        out_path=out_arg,
        allowlist=allow,
        max_depth=max_depth,
        max_files=max_files,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_workspace_find_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("workspace-find", help="Search workspace with traversal-safe bounded scan.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--name", required=True, help="Case-insensitive filename substring to match.")
    ap.add_argument("--out", default=".cache/reports/workspace_find.v1.json", help="Output JSON path.")
    ap.add_argument("--max-depth", default="6", help="Max directory depth (default: 6).")
    ap.add_argument("--max-files", default="2000", help="Max files to scan (default: 2000).")
    ap.add_argument(
        "--allow",
        default=".cache",
        help="Comma-separated allowlist of subdirs under workspace-root (default: .cache).",
    )
    ap.set_defaults(func=cmd_workspace_find)
