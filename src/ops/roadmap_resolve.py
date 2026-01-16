from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.workspace_find import run_workspace_find


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
        return [".cache", "roadmaps", "docs"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if parts else [".cache", "roadmaps", "docs"]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(core_root: Path, path: Path) -> tuple[bool | None, str | None]:
    try:
        from src.roadmap.orchestrator_helpers import _load_and_validate_roadmap
    except Exception as exc:
        return None, f"VALIDATOR_IMPORT_FAILED: {exc}"
    try:
        _load_and_validate_roadmap(core_root, path)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _validate_heuristic(obj: Any) -> tuple[bool, str | None]:
    if not isinstance(obj, dict):
        return False, "ROADMAP_INVALID_TYPE"
    roadmap_id = obj.get("roadmap_id")
    milestones = obj.get("milestones")
    if not isinstance(roadmap_id, str) or not roadmap_id.strip():
        return False, "ROADMAP_ID_REQUIRED"
    if not isinstance(milestones, list):
        return False, "MILESTONES_REQUIRED"
    return True, None


def _evaluate_candidate(core_root: Path, workspace_root: Path, rel_path: str) -> dict[str, Any]:
    candidate = {
        "path": rel_path,
        "parse_ok": False,
        "schema_ok": False,
        "validation_mode": "none",
        "error": None,
    }
    try:
        abs_path = (workspace_root / rel_path).resolve()
        abs_path.relative_to(workspace_root.resolve())
    except Exception:
        candidate["error"] = "PATH_TRAVERSAL_BLOCKED"
        return candidate
    if not abs_path.exists() or not abs_path.is_file():
        candidate["error"] = "FILE_MISSING"
        return candidate
    try:
        obj = _load_json(abs_path)
    except Exception as exc:
        candidate["error"] = f"JSON_PARSE_FAILED: {exc}"
        return candidate
    candidate["parse_ok"] = True

    schema_ok, schema_error = _validate_schema(core_root, abs_path)
    if schema_ok is None:
        candidate["validation_mode"] = "heuristic"
        heuristic_ok, heuristic_error = _validate_heuristic(obj)
        candidate["schema_ok"] = bool(heuristic_ok)
        candidate["error"] = heuristic_error
        return candidate

    candidate["validation_mode"] = "schema"
    candidate["schema_ok"] = bool(schema_ok)
    candidate["error"] = schema_error
    return candidate


def run_roadmap_resolve(
    *,
    workspace_root: Path,
    name: str,
    out_path: Path | str,
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        return {"status": "FAIL", "error_code": "NAME_REQUIRED"}

    out_resolved = _resolve_reports_path(workspace_root, str(out_path))
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    allow = allowlist if allowlist is not None else _parse_allowlist(None)
    find_out = workspace_root / ".cache" / "reports" / "workspace_find.v1.json"
    find_res = run_workspace_find(
        workspace_root=workspace_root,
        name=name,
        out_path=find_out,
        allowlist=allow,
        max_depth=6,
        max_files=2000,
    )
    find_status = str(find_res.get("status") or "")
    if find_status != "OK":
        payload = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": "WORKSPACE_FIND_FAILED",
            "find_status": find_status,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
        }
        out_resolved.parent.mkdir(parents=True, exist_ok=True)
        out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return payload

    try:
        find_report = _load_json(find_out)
    except Exception as exc:
        payload = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": f"WORKSPACE_FIND_REPORT_INVALID: {exc}",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
        }
        out_resolved.parent.mkdir(parents=True, exist_ok=True)
        out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return payload

    matches = find_report.get("matches") if isinstance(find_report, dict) else None
    if not isinstance(matches, list):
        matches = []
    json_candidates = sorted(
        {
            str(m).strip()
            for m in matches
            if isinstance(m, str) and str(m).strip().lower().endswith(".json")
        }
    )

    core_root = repo_root().resolve()
    candidates = [_evaluate_candidate(core_root, workspace_root, rel) for rel in json_candidates]
    candidates.sort(key=lambda item: item.get("path") or "")
    valid_paths = [c["path"] for c in candidates if c.get("parse_ok") and c.get("schema_ok")]
    chosen = sorted(valid_paths)[0] if valid_paths else None

    status = "OK"
    error_code = None
    if not candidates:
        status = "WARN"
        error_code = "NO_JSON_CANDIDATES"
    elif not chosen:
        status = "WARN"
        error_code = "NO_VALID_ROADMAP"

    try:
        out_rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
        find_rel = find_out.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        out_rel = str(out_resolved)
        find_rel = str(find_out)

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "query": {"name": name, "allowlist": allow},
        "workspace_find_report": find_rel,
        "candidate_count": len(candidates),
        "valid_count": len(valid_paths),
        "candidates": candidates,
        "chosen_path": chosen,
        "status": status,
        "error_code": error_code,
        "evidence_paths": [out_rel, find_rel],
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
    }

    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def cmd_roadmap_resolve(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    name = str(args.name or "")
    allow = _parse_allowlist(str(getattr(args, "allow", "") or ""))
    out_arg = str(args.out or ".cache/reports/roadmap_resolve.v1.json")
    result = run_roadmap_resolve(workspace_root=ws, name=name, out_path=out_arg, allowlist=allow)
    status = str(result.get("status") or "")
    print(json.dumps({k: result.get(k) for k in ("status", "chosen_path", "error_code", "candidate_count", "valid_count", "evidence_paths")}, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN"} else 2


def register_roadmap_resolve_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("roadmap-resolve", help="Resolve a valid roadmap path deterministically.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--name", default="roadmap", help="Name substring to search (default: roadmap).")
    ap.add_argument("--out", default=".cache/reports/roadmap_resolve.v1.json", help="Output JSON path.")
    ap.add_argument(
        "--allow",
        default=".cache,roadmaps,docs",
        help="Comma-separated allowlist under workspace-root (default: .cache,roadmaps,docs).",
    )
    ap.set_defaults(func=cmd_roadmap_resolve)
