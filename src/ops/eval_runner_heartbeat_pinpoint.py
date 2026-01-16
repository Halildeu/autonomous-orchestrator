from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.ops.commands.common import repo_root, warn

_HIT_PATTERN = re.compile(
    r"(heartbeat_stale_seconds_gt|gap_rules\.heartbeat_stale_seconds_gt|policy_north_star_operability|"
    r"heartbeat_stale_seconds_(warn|fail)|thresholds?)",
    re.IGNORECASE,
)
_DEF_PATTERN = re.compile(r"^\s*(def|class)\s+([A-Za-z0-9_]+)")
_KEY_PATTERN = re.compile(r'get\("([A-Za-z0-9_]+)"\)|\[\s*"([A-Za-z0-9_]+)"\s*\]')
_ASSIGN_PATTERN = re.compile(r'\b[A-Za-z0-9_]+\s*=\s*"([A-Za-z0-9_]+)"')
_JSON_PATH_PATTERN = re.compile(r"[A-Za-z0-9_./-]+\.v1\.json", re.IGNORECASE)
_THRESHOLD_TOKEN_PATTERN = re.compile(
    r"(heartbeat_stale_seconds_(warn|fail)|thresholds?|policy_north_star_operability)",
    re.IGNORECASE,
)
_PREFERRED_KEY_ORDER = ["last_tick_at", "updated_at", "last_status_at", "last_heartbeat_at", "ts"]


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


def _resolve_existing_cache_path(workspace_root: Path, path_arg: str) -> str | None:
    raw = Path(str(path_arg or "").strip())
    if not str(raw):
        return None
    candidate = raw if raw.is_absolute() else (workspace_root / raw)
    candidate_abs = candidate.absolute()
    cache_root = (workspace_root / ".cache").absolute()
    repo = repo_root().resolve()
    try:
        candidate_abs.relative_to(cache_root)
    except Exception:
        return None
    if not candidate_abs.exists():
        try:
            rel = candidate_abs.relative_to(repo).as_posix()
        except Exception:
            rel = ""
        rel_exists = bool(rel) and Path(rel).exists()
        try:
            parent = candidate_abs.parent
            list_exists = parent.is_dir() and candidate_abs.name in {p.name for p in parent.iterdir()}
        except Exception:
            list_exists = False
        if not rel_exists and not list_exists:
            return None
    try:
        rel = candidate_abs.relative_to(workspace_root.absolute()).as_posix()
    except Exception:
        rel = candidate_abs.as_posix()
    return rel


def _load_real_choice_path(workspace_root: Path) -> str | None:
    report_path = workspace_root / ".cache" / "reports" / "heartbeat_real_source_choice.v0.1.json"
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    chosen = data.get("chosen_path")
    if not isinstance(chosen, str) or not chosen.strip():
        return None
    return _resolve_existing_cache_path(workspace_root, chosen.strip())


def _find_test_tmp_heartbeat_path(workspace_root: Path) -> str | None:
    base = workspace_root / ".cache" / "test_tmp"
    if not base.exists():
        return None
    candidates: list[str] = []
    for name in ("airunner_heartbeat.v1.json", "airrunner_heartbeat.v1.json"):
        for path in sorted(base.rglob(name)):
            if not path.exists():
                continue
            try:
                rel = path.resolve().relative_to(workspace_root.resolve()).as_posix()
            except Exception:
                continue
            if not rel.startswith(".cache/test_tmp/"):
                continue
            if "/.cache/airunner/airrunner_heartbeat.v1.json" not in rel:
                continue
            candidates.append(rel)
    if not candidates:
        return None

    prefer = ["airunner_heartbeat", "airrunner_heartbeat", "/airunner/", "operability", "heartbeat_state", ".cache/airunner"]
    avoid = [
        "/eval_runner_",
        "/heartbeat_reconcile_",
        "/heartbeat_minimal_",
        "/policy_rule_extract_",
        "/policy_thresholds_map_",
    ]

    def score(path: str) -> tuple[int, str]:
        s = 0
        lower = path.lower()
        for token in prefer:
            if token in lower:
                s += 10
        for token in avoid:
            if token in lower:
                s -= 5
        return (s, path)

    ranked = sorted([score(p) for p in candidates], key=lambda item: (-item[0], item[1]))
    return ranked[0][1]


def _nearest_symbol(lines: list[str], start: int) -> dict[str, Any] | None:
    for idx in range(start, -1, -1):
        match = _DEF_PATTERN.match(lines[idx])
        if match:
            return {"kind": match.group(1), "name": match.group(2), "line": idx + 1}
    return None


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
            or "tick" in key_lower
            or key_lower.endswith("_at")
        ):
            keys.add(key)
    for key in _ASSIGN_PATTERN.findall(snippet):
        key_lower = key.lower()
        if (
            "time" in key_lower
            or key_lower == "ts"
            or "tick" in key_lower
            or key_lower.endswith("_at")
        ):
            keys.add(key)
    return sorted(keys)


def _extract_json_paths(snippet: str) -> list[str]:
    return sorted(set(match.group(0) for match in _JSON_PATH_PATTERN.finditer(snippet)))


def _extract_threshold_tokens(snippet: str) -> list[str]:
    return sorted(set(match.group(0) for match in _THRESHOLD_TOKEN_PATTERN.finditer(snippet)))


def _extract_contexts(lines: list[str], max_contexts: int = 10) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        if not _HIT_PATTERN.search(line):
            continue
        start = max(0, idx - 12)
        end = min(len(lines), idx + 13)
        snippet = "\n".join(lines[start:end])
        json_paths = _extract_json_paths(snippet)
        contexts.append(
            {
                "hit_line": idx + 1,
                "line_range": [start + 1, end],
                "nearest_symbol": _nearest_symbol(lines, idx),
                "keys_in_snippet": _extract_keys(snippet),
                "json_paths_in_snippet": json_paths,
                "heartbeat_paths_in_snippet": [p for p in json_paths if "heartbeat" in p.lower()],
                "threshold_tokens_in_snippet": _extract_threshold_tokens(snippet),
                "snippet": snippet,
            }
        )
        if len(contexts) >= max_contexts:
            break
    return contexts


def _select_read_path(paths: Iterable[str]) -> str | None:
    candidates = {p for p in paths if isinstance(p, str) and p.strip()}
    if not candidates:
        return None

    prefer = ["airrunner_heartbeat", "/airunner/", "operability", "heartbeat_state", ".cache/airunner"]
    avoid = ["policy_rule_extract", "threshold", "contract", "test_tmp", "reports"]

    def score(path: str) -> tuple[int, str]:
        lower = path.lower()
        s = 0
        for token in prefer:
            if token in lower:
                s += 10
        for token in avoid:
            if token in lower:
                s -= 5
        return (s, path)

    ranked = sorted([score(p) for p in candidates], key=lambda item: (-item[0], item[1]))
    return ranked[0][1] if ranked else None


def _select_read_key(keys: Iterable[str]) -> str | None:
    candidates = {k for k in keys if isinstance(k, str) and k.strip()}
    if not candidates:
        return None
    for candidate in _PREFERRED_KEY_ORDER:
        if candidate in candidates:
            return candidate
    return sorted(candidates)[0]


def _iter_src_files(src_root: Path) -> Iterable[Path]:
    for path in sorted(src_root.rglob("*.py")):
        yield path


def run_eval_runner_heartbeat_pinpoint(
    *,
    workspace_root: Path,
    out_json: Path | str,
    out_md: Path | str,
    max_files: int = 5,
    repo_root_override: Path | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    out_json_resolved = _resolve_reports_path(workspace_root, str(out_json))
    out_md_resolved = _resolve_reports_path(workspace_root, str(out_md))
    if out_json_resolved is None or out_md_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    repo = (repo_root_override or repo_root()).resolve()
    src_root = (repo / "src").resolve()
    if not src_root.exists() or not src_root.is_dir():
        return {"status": "FAIL", "error_code": "SRC_ROOT_NOT_FOUND"}

    freq: dict[str, int] = {}
    file_snippets: dict[str, list[dict[str, Any]]] = {}
    candidate_input_keys: set[str] = set()
    candidate_threshold_refs: set[str] = set()
    candidate_heartbeat_paths: set[str] = set()

    for path in _iter_src_files(src_root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        hit_lines = [idx for idx, line in enumerate(lines) if _HIT_PATTERN.search(line)]
        if not hit_lines:
            continue
        rel_path = path.resolve().relative_to(repo).as_posix()
        freq[rel_path] = len(hit_lines)
        contexts = _extract_contexts(lines)
        file_snippets[rel_path] = contexts
        for ctx in contexts:
            for key in ctx.get("keys_in_snippet") or []:
                candidate_input_keys.add(key)
            for token in ctx.get("threshold_tokens_in_snippet") or []:
                candidate_threshold_refs.add(token)
            for hb_path in ctx.get("heartbeat_paths_in_snippet") or []:
                candidate_heartbeat_paths.add(hb_path)

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    top_files = ranked[: max_files if max_files > 0 else 0]

    results: list[dict[str, Any]] = []
    for path, count in top_files:
        results.append(
            {
                "path": path,
                "exists": True,
                "hit_count": count,
                "contexts": file_snippets.get(path, []),
            }
        )

    test_tmp_choice = _find_test_tmp_heartbeat_path(workspace_root)
    real_choice_path = _load_real_choice_path(workspace_root)
    existing_paths = sorted(
        {
            rel
            for p in candidate_heartbeat_paths
            if (rel := _resolve_existing_cache_path(workspace_root, p)) is not None
        }
    )

    declared_rule_path = _select_read_path(candidate_heartbeat_paths)
    declared_rule_key = _select_read_key(candidate_input_keys)
    declared_rule_path_resolved = (
        _resolve_existing_cache_path(workspace_root, declared_rule_path)
        if declared_rule_path
        else None
    )

    eval_runner_read_key = declared_rule_key
    eval_runner_read_key_source = "declared_rule_key"

    eval_runner_read_path = None
    eval_runner_read_path_source = None
    if declared_rule_path_resolved:
        eval_runner_read_path = declared_rule_path_resolved
        eval_runner_read_path_source = "declared_rule_path_resolved"
    elif isinstance(declared_rule_path, str) and declared_rule_path.strip().startswith(".cache/"):
        eval_runner_read_path = declared_rule_path.strip()
        eval_runner_read_path_source = "declared_rule_path"

    payload = {
        "version": "v1",
        "generated_at": now_iso or _now_iso(),
        "workspace_root": str(workspace_root),
        "patterns": sorted(set([p for p in _HIT_PATTERN.pattern.split("|") if p])),
        "top_files": [{"path": p, "hit_count": c} for p, c in top_files],
        "results": results,
        "declared_rule_path": declared_rule_path,
        "declared_rule_key": declared_rule_key,
        "declared_rule_path_resolved": declared_rule_path_resolved,
        "test_tmp_heartbeat_path": test_tmp_choice,
        "eval_runner_read_path": eval_runner_read_path
        or real_choice_path
        or _select_read_path(existing_paths),
        "eval_runner_read_path_source": eval_runner_read_path_source,
        "eval_runner_read_key": eval_runner_read_key,
        "eval_runner_read_key_source": eval_runner_read_key_source,
        "candidate_input_keys": sorted(candidate_input_keys),
        "candidate_threshold_refs": sorted(candidate_threshold_refs),
        "candidate_heartbeat_paths": sorted(candidate_heartbeat_paths),
        "candidate_heartbeat_paths_existing": existing_paths,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "READ_ONLY=true"],
    }

    out_json_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_json_resolved.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    md_lines: list[str] = ["# Eval runner heartbeat pinpoint (v1)", ""]
    for entry in results:
        md_lines.append(f"## {entry.get('path')}")
        contexts = entry.get("contexts") or []
        for ctx in contexts[:5]:
            sym = ctx.get("nearest_symbol") or {}
            md_lines.append(
                f"- hit_line: {ctx.get('hit_line')} | range: {ctx.get('line_range')} | "
                f"symbol: {sym.get('kind','?')} {sym.get('name','?')} @ {sym.get('line','?')}"
            )
            md_lines.append(f"  keys: {ctx.get('keys_in_snippet')}")
            md_lines.append(f"  json_paths: {ctx.get('json_paths_in_snippet')}")
            md_lines.append(f"  threshold_tokens: {ctx.get('threshold_tokens_in_snippet')}")
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


def cmd_eval_runner_heartbeat_pinpoint(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    out_json = str(args.out_json or ".cache/reports/eval_runner_heartbeat_pinpoint.v1.json")
    out_md = str(args.out_md or ".cache/reports/eval_runner_heartbeat_pinpoint.v1.md")
    try:
        max_files = int(args.max_files)
    except Exception:
        warn("FAIL error=INVALID_MAX_FILES")
        return 2

    result = run_eval_runner_heartbeat_pinpoint(
        workspace_root=ws,
        out_json=out_json,
        out_md=out_md,
        max_files=max_files,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_eval_runner_heartbeat_pinpoint_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "eval-runner-heartbeat-pinpoint",
        help="Pinpoint eval_runner heartbeat wiring (read-only, deterministic).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument(
        "--out-json",
        default=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        help="Output JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--out-md",
        default=".cache/reports/eval_runner_heartbeat_pinpoint.v1.md",
        help="Output Markdown path under workspace .cache/reports.",
    )
    ap.add_argument("--max-files", default="5", help="Max source files to analyze.")
    ap.set_defaults(func=cmd_eval_runner_heartbeat_pinpoint)
