from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn

_JSON_PATH_PATTERN = re.compile(r"[A-Za-z0-9_./-]+\.v1\.json", re.IGNORECASE)
_HEARTBEAT_FILE_PATTERN = re.compile(r"heartbeat.*\.v1\.json$", re.IGNORECASE)
_THRESHOLD_REF_PATTERN = re.compile(r"(threshold|warn|fail|ref|key)", re.IGNORECASE)
_THRESHOLD_TOKEN_PATTERN = re.compile(r"heartbeat_stale_seconds_(warn|fail)", re.IGNORECASE)
_GENERIC_THRESHOLD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]*threshold[A-Za-z0-9_]*", re.IGNORECASE)
_TIMESTAMP_KEY_PATTERN = re.compile(r"(tick|heartbeat|updated|timestamp|_at$)", re.IGNORECASE)
_TIMESTAMP_KEY_REGEX = re.compile(r"^[A-Za-z0-9_]+$")

_KNOWN_TIMESTAMP_KEYS = {
    "last_tick_at",
    "updated_at",
    "last_heartbeat_at",
    "tick_id",
    "ts",
}


def _now_iso(now_override: str | None = None) -> str:
    if now_override:
        return now_override
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


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


def _is_heartbeat_file(value: str) -> bool:
    lower = value.lower().strip()
    return "heartbeat" in lower and lower.endswith(".v1.json") and bool(_HEARTBEAT_FILE_PATTERN.search(lower))


def _is_timestamp_key(value: str) -> bool:
    if value in _KNOWN_TIMESTAMP_KEYS:
        return True
    if value.endswith("_at") or value.lower() in _KNOWN_TIMESTAMP_KEYS:
        return True
    return bool(_TIMESTAMP_KEY_PATTERN.search(value))


def _is_threshold_ref(value: str) -> bool:
    return bool(_THRESHOLD_REF_PATTERN.search(value))


def _load_real_source_choice(workspace_root: Path) -> str | None:
    report_path = workspace_root / ".cache" / "reports" / "heartbeat_real_source_choice.v0.1.json"
    data = _load_json(report_path)
    if not isinstance(data, dict):
        return None
    chosen = data.get("chosen_path")
    if not isinstance(chosen, str) or not chosen.strip():
        return None
    resolved = _resolve_candidate_path(workspace_root, chosen.strip())
    if resolved is None:
        return None
    try:
        rel = resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = resolved.as_posix()
    if not rel.startswith(".cache/"):
        return None
    return rel


def _walk_payload(obj: Any, candidates: dict[str, set[str]]) -> None:
    if isinstance(obj, dict):
        for key in sorted(obj.keys(), key=lambda k: str(k)):
            key_str = str(key)
            if _is_timestamp_key(key_str):
                candidates["timestamp_keys"].add(key_str)
            _walk_payload(obj[key], candidates)
    elif isinstance(obj, list):
        for item in obj:
            _walk_payload(item, candidates)
    elif isinstance(obj, str):
        if _is_heartbeat_file(obj):
            candidates["input_files"].add(obj)
        for match in _JSON_PATH_PATTERN.findall(obj):
            if "heartbeat" in match.lower():
                candidates["input_files"].add(match)
        if _is_timestamp_key(obj):
            candidates["timestamp_keys"].add(obj)
        for token in _THRESHOLD_TOKEN_PATTERN.finditer(obj):
            candidates["threshold_refs"].add(token.group(0))
        for token in _GENERIC_THRESHOLD_TOKEN_PATTERN.finditer(obj):
            candidates["threshold_refs"].add(token.group(0))


def _collect_snippets(payload: dict[str, Any], max_snippets: int = 10) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return snippets
    for entry in sorted(results, key=lambda item: str(item.get("path") or "")):
        contexts = entry.get("contexts")
        if not isinstance(contexts, list):
            continue
        for ctx in contexts:
            if len(snippets) >= max_snippets:
                break
            if not isinstance(ctx, dict):
                continue
            snippet = ctx.get("snippet")
            if not isinstance(snippet, str) or not snippet.strip():
                continue
            snippets.append(
                {
                    "path": entry.get("path"),
                    "hit_line": ctx.get("hit_line"),
                    "snippet": snippet[:320],
                }
            )
        if len(snippets) >= max_snippets:
            break
    return snippets


def _select_input_file(files: list[str]) -> str | None:
    if not files:
        return None
    preferred = [f for f in files if "airrunner" in f.lower() and "heartbeat" in f.lower()]
    if preferred:
        return sorted(preferred)[0]
    return sorted(files)[0]


def _select_timestamp_key(keys: list[str]) -> str | None:
    if not keys:
        return None
    if "last_tick_at" in keys:
        return "last_tick_at"
    return sorted(keys)[0]


def _select_threshold_ref(refs: list[str]) -> str | None:
    if not refs:
        return None
    heartbeat_refs = [ref for ref in refs if "heartbeat" in ref.lower()]
    if heartbeat_refs:
        return sorted(heartbeat_refs)[0]
    return sorted(refs)[0]


def _validate_selection(workspace_root: Path, selected_input: str, selected_key: str) -> tuple[bool, str | None]:
    if not _TIMESTAMP_KEY_REGEX.match(selected_key):
        return False, "TIMESTAMP_KEY_INVALID"
    resolved = _resolve_candidate_path(workspace_root, selected_input)
    if resolved is None:
        return False, "INPUT_PATH_INVALID"
    try:
        rel = resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = resolved.as_posix()
    if not rel.startswith(".cache/"):
        return False, "INPUT_PATH_OUTSIDE_CACHE"
    return True, None


def run_eval_runner_heartbeat_select(
    *,
    workspace_root: Path,
    pinpoint_path: Path | str,
    out_path: Path | str,
    now_iso: str | None = None,
) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}
    pinpoint_resolved = _resolve_reports_path(workspace_root, str(pinpoint_path))
    if pinpoint_resolved is None:
        return {"status": "FAIL", "error_code": "PINPOINT_PATH_INVALID"}
    if not pinpoint_resolved.exists():
        return {"status": "FAIL", "error_code": "PINPOINT_INPUT_MISSING"}

    try:
        payload = json.loads(pinpoint_resolved.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "FAIL", "error_code": "PINPOINT_INVALID"}

    candidates: dict[str, set[str]] = {
        "input_files": set(),
        "timestamp_keys": set(),
        "threshold_refs": set(),
    }
    _walk_payload(payload, candidates)

    input_files = sorted(candidates["input_files"])
    timestamp_keys = sorted(candidates["timestamp_keys"])
    threshold_refs = sorted(candidates["threshold_refs"])

    explicit_path = payload.get("eval_runner_read_path")
    explicit_key = payload.get("eval_runner_read_key")
    if not isinstance(explicit_path, str) or not explicit_path.strip():
        return {"status": "FAIL", "error_code": "PINPOINT_READ_PATH_MISSING"}
    if not isinstance(explicit_key, str) or not explicit_key.strip():
        return {"status": "FAIL", "error_code": "PINPOINT_READ_KEY_MISSING"}

    selected_input_file = explicit_path.strip()
    selected_timestamp_key = explicit_key.strip()
    selected_threshold_ref = _select_threshold_ref(threshold_refs)

    valid, error_code = _validate_selection(workspace_root, selected_input_file, selected_timestamp_key)
    if not valid:
        return {"status": "FAIL", "error_code": error_code}

    result = {
        "version": "v1",
        "generated_at": _now_iso(now_iso),
        "workspace_root": str(workspace_root),
        "pinpoint_path": str(pinpoint_resolved),
        "selected_input_file": selected_input_file,
        "selected_timestamp_key": selected_timestamp_key,
        "selected_threshold_ref": selected_threshold_ref,
        "candidate_input_files": input_files[:50],
        "candidate_timestamp_keys": timestamp_keys[:50],
        "candidate_threshold_refs": threshold_refs[:50],
        "explicit_fields_used": True,
        "evidence_snippets": _collect_snippets(payload, max_snippets=8),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "READ_ONLY=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(
        json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)
    return {"status": "OK", "report_path": rel}


def cmd_eval_runner_heartbeat_select(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    pinpoint_arg = str(args.input or ".cache/reports/eval_runner_heartbeat_pinpoint.v1.json")
    out_arg = str(args.out or ".cache/reports/eval_runner_heartbeat_exact_selection.v1.json")

    result = run_eval_runner_heartbeat_select(
        workspace_root=ws,
        pinpoint_path=pinpoint_arg,
        out_path=out_arg,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_eval_runner_heartbeat_select_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "eval-runner-heartbeat-select",
        help="Select deterministic heartbeat input path/key from pinpoint report (read-only).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument(
        "--in",
        dest="input",
        default=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        help="Pinpoint JSON path under workspace .cache/reports.",
    )
    ap.add_argument(
        "--out",
        default=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        help="Output JSON path under workspace .cache/reports.",
    )
    ap.set_defaults(func=cmd_eval_runner_heartbeat_select)
