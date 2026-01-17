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


def _resolve_reports_path(workspace_root: Path, arg: str) -> Path | None:
    raw = Path(str(arg or "").strip())
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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_thresholds_table(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    matches = payload.get("matches")
    if isinstance(matches, list):
        for match in matches:
            if not isinstance(match, dict):
                continue
            subtree = match.get("extracted_subtree")
            if isinstance(subtree, dict):
                return subtree, str(match.get("path") or "")
    return None, None


def _extract_rule_references(payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    matches = payload.get("matches")
    if isinstance(matches, list):
        for match in matches:
            if not isinstance(match, dict):
                continue
            value = match.get("extracted_subtree")
            if isinstance(value, str):
                refs.append(
                    {
                        "value": value,
                        "source_path": str(match.get("path") or ""),
                    }
                )
    extra_keys = payload.get("all_referenced_keys")
    if isinstance(extra_keys, list):
        for key in extra_keys:
            if isinstance(key, str):
                refs.append({"value": key, "source_path": "all_referenced_keys"})
    seen = set()
    deduped: list[dict[str, Any]] = []
    for ref in refs:
        val = ref.get("value")
        if not isinstance(val, str):
            continue
        if val in seen:
            continue
        seen.add(val)
        deduped.append(ref)
    return deduped


def run_policy_thresholds_map(
    *,
    workspace_root: Path,
    thresholds_path: Path | str,
    rule_path: Path | str,
    out_path: Path | str,
) -> dict[str, Any]:
    thresholds_resolved = _resolve_reports_path(workspace_root, str(thresholds_path))
    if thresholds_resolved is None:
        return {"status": "FAIL", "error_code": "THRESHOLDS_PATH_INVALID"}
    rule_resolved = _resolve_reports_path(workspace_root, str(rule_path))
    if rule_resolved is None:
        return {"status": "FAIL", "error_code": "RULE_PATH_INVALID"}
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    thresholds_payload = _load_json(thresholds_resolved)
    if thresholds_payload is None:
        return {"status": "FAIL", "error_code": "THRESHOLDS_INVALID"}
    rule_payload = _load_json(rule_resolved)
    if rule_payload is None:
        return {"status": "FAIL", "error_code": "RULE_INVALID"}

    thresholds_table, thresholds_match_path = _extract_thresholds_table(thresholds_payload)
    if thresholds_table is None:
        return {"status": "FAIL", "error_code": "THRESHOLDS_TABLE_NOT_FOUND"}

    references = _extract_rule_references(rule_payload)
    if not references:
        return {"status": "FAIL", "error_code": "RULE_REFERENCES_NOT_FOUND"}

    resolved_map: dict[str, Any] = {}
    resolved_numeric: dict[str, float] = {}
    unresolved: list[dict[str, Any]] = []
    for ref in references:
        key = ref.get("value")
        if not isinstance(key, str):
            continue
        if key in thresholds_table:
            value = thresholds_table.get(key)
            resolved_map[key] = value
            if isinstance(value, (int, float)):
                resolved_numeric[key] = float(value)
            ref["resolved_value"] = value
        else:
            unresolved.append(ref)

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "thresholds_path": str(thresholds_resolved),
        "rule_path": str(rule_resolved),
        "thresholds_match_path": thresholds_match_path,
        "reference_count": len(references),
        "references": references,
        "resolved_thresholds": {k: resolved_map[k] for k in sorted(resolved_map)},
        "resolved_threshold_seconds": {k: resolved_numeric[k] for k in sorted(resolved_numeric)},
        "unresolved_references": unresolved,
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
    return {"status": "OK", "report_path": rel, "resolved_count": len(resolved_map)}


def cmd_policy_thresholds_map(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    thresholds_arg = str(args.thresholds or "")
    rule_arg = str(args.rule or "")
    out_arg = str(args.out or ".cache/reports/policy_thresholds_map.v1.json")

    result = run_policy_thresholds_map(
        workspace_root=ws,
        thresholds_path=thresholds_arg,
        rule_path=rule_arg,
        out_path=out_arg,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_policy_thresholds_map_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "policy-thresholds-map",
        help="Resolve rule references to numeric thresholds (read-only, deterministic).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--thresholds", required=True, help="Thresholds extract path under workspace reports.")
    ap.add_argument("--rule", required=True, help="Rule extract path under workspace reports.")
    ap.add_argument("--out", default=".cache/reports/policy_thresholds_map.v1.json", help="Output JSON path.")
    ap.set_defaults(func=cmd_policy_thresholds_map)
