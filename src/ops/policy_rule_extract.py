from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn

_JSON_PATH_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\.json", re.IGNORECASE)
_KEY_HINT_PATTERN = re.compile(r"(heartbeat|stale|threshold|tick|time)", re.IGNORECASE)


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


def _resolve_policy_path(policy_arg: str) -> Path | None:
    root = repo_root().resolve()
    raw = Path(str(policy_arg or "").strip())
    if not str(raw):
        return None
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if not candidate.exists():
        if raw.name == raw.as_posix():
            alt = (root / "policies" / raw).resolve()
            if alt.exists():
                candidate = alt
    try:
        candidate.relative_to(root)
    except Exception:
        return None
    return candidate if candidate.exists() else None


def _collect_literals(value: Any) -> tuple[list[float], list[str], list[str]]:
    numbers: set[float] = set()
    paths: set[str] = set()
    keys: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k in sorted(obj.keys()):
                key = str(k)
                if _KEY_HINT_PATTERN.search(key):
                    keys.add(key)
                walk(obj[k])
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, (int, float)):
            numbers.add(float(obj))
        elif isinstance(obj, str):
            if _JSON_PATH_PATTERN.search(obj) or ".cache/" in obj:
                paths.add(obj)

    walk(value)
    return (
        sorted(numbers),
        sorted(paths),
        sorted(keys),
    )


def _extract_rule_matches(payload: Any, rule_key: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    def walk(obj: Any, path: list[str]) -> None:
        if isinstance(obj, dict):
            for key in sorted(obj.keys()):
                value = obj[key]
                next_path = path + [str(key)]
                if str(key) == rule_key:
                    numbers, paths, keys = _collect_literals(value)
                    matches.append(
                        {
                            "path": ".".join(next_path),
                            "path_tokens": next_path,
                            "value_type": type(value).__name__,
                            "extracted_subtree": value,
                            "numeric_literals": numbers,
                            "referenced_paths": paths,
                            "referenced_keys": keys,
                        }
                    )
                walk(value, next_path)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                walk(item, path + [str(idx)])

    walk(payload, [])
    return matches


def run_policy_rule_extract(
    *,
    workspace_root: Path,
    policy_path: Path | str,
    rule_key: str,
    out_path: Path | str,
    out_md: Path | str | None = None,
) -> dict[str, Any]:
    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    policy_resolved = _resolve_policy_path(str(policy_path))
    if policy_resolved is None:
        return {"status": "FAIL", "error_code": "POLICY_PATH_INVALID"}

    if not rule_key:
        return {"status": "FAIL", "error_code": "RULE_KEY_REQUIRED"}

    try:
        policy_obj = json.loads(policy_resolved.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "FAIL", "error_code": "POLICY_INVALID"}

    matches = _extract_rule_matches(policy_obj, rule_key)
    if not matches:
        return {"status": "FAIL", "error_code": "RULE_KEY_NOT_FOUND"}

    all_numbers: set[float] = set()
    all_paths: set[str] = set()
    all_keys: set[str] = set()
    for match in matches:
        for num in match.get("numeric_literals") or []:
            try:
                all_numbers.add(float(num))
            except Exception:
                continue
        for p in match.get("referenced_paths") or []:
            all_paths.add(str(p))
        for k in match.get("referenced_keys") or []:
            all_keys.add(str(k))

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_resolved),
        "rule_key": rule_key,
        "match_count": len(matches),
        "matches": matches,
        "all_numeric_literals": sorted(all_numbers),
        "all_referenced_paths": sorted(all_paths),
        "all_referenced_keys": sorted(all_keys),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "READ_ONLY=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    if out_md:
        md_resolved = _resolve_reports_path(workspace_root, str(out_md))
        if md_resolved is None:
            return {"status": "FAIL", "error_code": "OUT_MD_PATH_INVALID"}
        md_lines: list[str] = [
            "# Policy rule extract",
            "",
            f"- policy_path: {policy_resolved}",
            f"- rule_key: {rule_key}",
            f"- match_count: {len(matches)}",
            "",
            "## Matches",
        ]
        for match in matches[:10]:
            md_lines.append(f"- {match.get('path')}")
        md_resolved.parent.mkdir(parents=True, exist_ok=True)
        md_resolved.write_text("\n".join(md_lines), encoding="utf-8")

    try:
        rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        rel = str(out_resolved)
    return {"status": "OK", "report_path": rel, "match_count": len(matches)}


def cmd_policy_rule_extract(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    policy_arg = str(args.policy or "")
    rule_key = str(args.rule_key or "")
    out_arg = str(args.out or ".cache/reports/policy_rule_extract.v1.json")
    out_md = str(args.out_md or "") or None

    result = run_policy_rule_extract(
        workspace_root=ws,
        policy_path=policy_arg,
        rule_key=rule_key,
        out_path=out_arg,
        out_md=out_md,
    )
    if result.get("status") != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def register_policy_rule_extract_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser(
        "policy-rule-extract",
        help="Extract rule subtree from a policy file (read-only, deterministic).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--policy", required=True, help="Policy file path (under repo root).")
    ap.add_argument("--rule-key", required=True, help="Rule key to extract.")
    ap.add_argument("--out", default=".cache/reports/policy_rule_extract.v1.json", help="Output JSON path.")
    ap.add_argument("--out-md", default="", help="Optional output Markdown path.")
    ap.set_defaults(func=cmd_policy_rule_extract)
