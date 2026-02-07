from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn

_HIT_PATTERN = re.compile(
    r"(heartbeat_stale_seconds_gt|stale_seconds|heartbeat|airrunner_heartbeat)",
    re.IGNORECASE,
)
_DEF_PATTERN = re.compile(r"^\s*(def|class)\s+([A-Za-z0-9_]+)")
_KEY_PATTERN = re.compile(r'get\("([A-Za-z0-9_]+)"\)|\[\s*"([A-Za-z0-9_]+)"\s*\]')


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


def _extract_keys(snippet: str) -> list[str]:
    keys: set[str] = set()
    for a, b in _KEY_PATTERN.findall(snippet):
        key = a or b
        if not key:
            continue
        key_lower = key.lower()
        if (
            "time" in key_lower
            or key_lower == "ts"
            or "heartbeat" in key_lower
            or "tick" in key_lower
            or key_lower.endswith("_at")
        ):
            keys.add(key)
    return sorted(keys)


def _nearest_symbol(lines: list[str], start: int) -> dict[str, Any] | None:
    for idx in range(start, -1, -1):
        match = _DEF_PATTERN.match(lines[idx])
        if match:
            return {"kind": match.group(1), "name": match.group(2), "line": idx + 1}
    return None


def _extract_contexts(lines: list[str], max_contexts: int = 10) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        if not _HIT_PATTERN.search(line):
            continue
        start = max(0, idx - 12)
        end = min(len(lines), idx + 13)
        snippet = "\n".join(lines[start:end])
        contexts.append(
            {
                "hit_line": idx + 1,
                "line_range": [start + 1, end],
                "nearest_symbol": _nearest_symbol(lines, idx),
                "keys_in_snippet": _extract_keys(snippet),
                "snippet": snippet,
            }
        )
        if len(contexts) >= max_contexts:
            break
    return contexts


def run_heartbeat_checker_pinpoint(
    *,
    workspace_root: Path,
    probe_path: Path | str,
    out_json: Path | str,
    out_md: Path | str,
    max_files: int = 5,
) -> dict[str, Any]:
    out_json_resolved = _resolve_reports_path(workspace_root, str(out_json))
    out_md_resolved = _resolve_reports_path(workspace_root, str(out_md))
    if out_json_resolved is None or out_md_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    probe_resolved = _resolve_reports_path(workspace_root, str(probe_path))
    if probe_resolved is None:
        return {"status": "FAIL", "error_code": "PROBE_PATH_INVALID"}
    if not probe_resolved.exists():
        return {"status": "FAIL", "error_code": "PROBE_NOT_FOUND"}

    try:
        probe = json.loads(probe_resolved.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "FAIL", "error_code": "PROBE_INVALID"}

    hits = probe.get("hits", [])
    if not isinstance(hits, list):
        hits = []

    freq: dict[str, int] = {}
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        path = hit.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        freq[path] = freq.get(path, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    top_files = ranked[: max_files if max_files > 0 else 0]

    results: list[dict[str, Any]] = []
    ignored_paths: list[str] = []
    repo = repo_root().resolve()

    for path, _count in top_files:
        if not path.startswith("src/"):
            ignored_paths.append(path)
            results.append({"path": path, "exists": False, "contexts": []})
            continue
        target = (repo / path).resolve()
        try:
            target.relative_to(repo)
        except Exception:
            results.append({"path": path, "exists": False, "contexts": []})
            continue
        if not target.exists():
            results.append({"path": path, "exists": False, "contexts": []})
            continue
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        contexts = _extract_contexts(lines)
        results.append({"path": path, "exists": True, "contexts": contexts})

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "probe_path": str(probe_resolved),
        "top_files": [{"path": p, "hit_count": c} for p, c in top_files],
        "ignored_paths": sorted(set(ignored_paths)),
        "results": results,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "READ_ONLY=true"],
    }

    out_json_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_json_resolved.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    md_lines: list[str] = ["# Heartbeat checker pinpoint (v1)", ""]
    for entry in results:
        md_lines.append(f"## {entry.get('path')}")
        if not entry.get("exists"):
            md_lines.append("- missing file")
            md_lines.append("")
            continue
        contexts = entry.get("contexts") or []
        for ctx in contexts[:5]:
            sym = ctx.get("nearest_symbol") or {}
            md_lines.append(
                f"- hit_line: {ctx.get('hit_line')} | range: {ctx.get('line_range')} | "
                f"symbol: {sym.get('kind','?')} {sym.get('name','?')} @ {sym.get('line','?')}"
            )
            md_lines.append(f"  keys: {ctx.get('keys_in_snippet')}")
            md_lines.append("```")
            md_lines.append(str(ctx.get("snippet") or ""))
            md_lines.append("```")
        md_lines.append("")

    out_md_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_md_resolved.write_text("\n".join(md_lines), encoding="utf-8")

    try:
        rel = out_json_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_json_resolved)
    return {"status": "OK", "report_path": rel, "top_files_count": len(top_files)}


def cmd_heartbeat_checker_pinpoint(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    probe = str(args.input or ".cache/reports/heartbeat_checker_code_probe.v0.1-r2.json")
    out_json = str(args.out_json or ".cache/reports/heartbeat_checker_pinpoint.v1.json")
    out_md = str(args.out_md or ".cache/reports/heartbeat_checker_pinpoint.v1.md")
    try:
        max_files = int(args.max_files)
    except Exception:
        warn("FAIL error=INVALID_MAX_FILES")
        return 2

    result = run_heartbeat_checker_pinpoint(
        workspace_root=ws,
        probe_path=probe,
        out_json=out_json,
        out_md=out_md,
        max_files=max_files,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_heartbeat_checker_pinpoint_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "heartbeat-checker-pinpoint",
        help="Pinpoint heartbeat checker file/line/key from probe hits (read-only).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument(
        "--in",
        dest="input",
        default=".cache/reports/heartbeat_checker_code_probe.v0.1-r2.json",
        help="Probe JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--out-json",
        default=".cache/reports/heartbeat_checker_pinpoint.v1.json",
        help="Output JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--out-md",
        default=".cache/reports/heartbeat_checker_pinpoint.v1.md",
        help="Output Markdown path under workspace .cache/reports.",
    )
    ap.add_argument("--max-files", default="5", help="Max source files to analyze.")
    ap.set_defaults(func=cmd_heartbeat_checker_pinpoint)
