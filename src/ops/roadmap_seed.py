from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.trace_meta import build_run_id, build_trace_meta


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


def _resolve_out_path(workspace_root: Path, out_arg: str) -> Path | None:
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
    allowed_roots = [
        (workspace_root / ".cache" / "index").resolve(),
        (workspace_root / ".cache" / "reports").resolve(),
    ]
    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            return candidate
        except Exception:
            continue
    return None


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError("Expected boolean value true|false.")


def _build_seed_roadmap(title: str) -> dict[str, Any]:
    milestone_title = str(title or "").strip() or "Seed Milestone"
    return {
        "roadmap_id": "WORKSPACE_SEED",
        "version": "v1",
        "iso_core_required": False,
        "global_gates": [],
        "milestones": [
            {
                "id": "M1-SEED",
                "title": milestone_title,
                "steps": [{"type": "note", "text": "Seed roadmap placeholder."}],
                "gates": [],
                "dod": [],
            }
        ],
    }


def _validate_roadmap(core_root: Path, obj: dict[str, Any]) -> tuple[bool, list[str] | None]:
    try:
        from src.roadmap.compiler import validate_roadmap
    except Exception as exc:
        return False, [f"VALIDATOR_IMPORT_FAILED: {exc}"]

    schema_path = core_root / "schemas" / "roadmap.schema.json"
    if not schema_path.exists():
        return False, ["SCHEMA_NOT_FOUND"]

    errors = validate_roadmap(obj, schema_path)
    if errors:
        return False, errors
    return True, None


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run_roadmap_seed(
    *,
    workspace_root: Path,
    out_path: Path | str,
    title: str,
    force: bool,
) -> dict[str, Any]:
    out_resolved = _resolve_out_path(workspace_root, str(out_path))
    inputs = {"title": title, "out_path": str(out_path), "force": bool(force)}
    run_id = build_run_id(workspace_root=workspace_root, op_name="roadmap-seed", inputs=inputs)
    work_item_id = run_id

    evidence_paths: list[str] = []
    report_path = None
    if out_resolved is not None:
        try:
            report_path = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            report_path = str(out_resolved)
        if report_path:
            evidence_paths.append(report_path)

    trace_meta = build_trace_meta(
        work_item_id=work_item_id,
        work_item_kind="ROADMAP_SEED",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=evidence_paths,
        workspace_root=str(workspace_root),
    )

    if out_resolved is None:
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": "OUT_PATH_INVALID",
            "evidence_paths": evidence_paths,
            "trace_meta": trace_meta,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
        }

    roadmap = _build_seed_roadmap(title)
    schema_ok, schema_errors = _validate_roadmap(repo_root().resolve(), roadmap)
    if not schema_ok:
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": "ROADMAP_SCHEMA_INVALID",
            "validation_errors": schema_errors or [],
            "report_path": report_path,
            "evidence_paths": evidence_paths,
            "trace_meta": trace_meta,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
        }

    content = json.dumps(roadmap, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    existing_text = None
    if out_resolved.exists():
        try:
            existing_text = out_resolved.read_text(encoding="utf-8")
        except Exception as exc:
            return {
                "version": "v1",
                "generated_at": _now_iso(),
                "workspace_root": str(workspace_root),
                "status": "FAIL",
                "error_code": f"OUT_READ_FAILED: {exc}",
                "report_path": report_path,
                "evidence_paths": evidence_paths,
                "trace_meta": trace_meta,
                "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
            }

    if existing_text is not None and existing_text == content:
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "OK",
            "result": "ALREADY_DONE",
            "report_path": report_path,
            "roadmap_id": roadmap["roadmap_id"],
            "roadmap_version": roadmap["version"],
            "milestone_id": roadmap["milestones"][0]["id"],
            "evidence_paths": evidence_paths,
            "trace_meta": trace_meta,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
        }

    if existing_text is not None and not force:
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": "OUT_EXISTS_DIFFERENT",
            "report_path": report_path,
            "evidence_paths": evidence_paths,
            "trace_meta": trace_meta,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
        }

    _atomic_write_text(out_resolved, content)
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": "OK",
        "result": "CREATED" if existing_text is None else "OVERWRITTEN",
        "report_path": report_path,
        "roadmap_id": roadmap["roadmap_id"],
        "roadmap_version": roadmap["version"],
        "milestone_id": roadmap["milestones"][0]["id"],
        "evidence_paths": evidence_paths,
        "trace_meta": trace_meta,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
    }


def cmd_roadmap_seed(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    out_arg = str(args.out or ".cache/index/roadmap.v1.json")
    title = str(args.title or "")
    try:
        force = _parse_bool(str(args.force or "false"))
    except ValueError:
        warn("FAIL error=INVALID_FORCE")
        return 2

    result = run_roadmap_seed(workspace_root=ws, out_path=out_arg, title=title, force=force)
    status = str(result.get("status") or "")
    if status not in {"OK", "WARN"}:
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(
        json.dumps(
            {k: result.get(k) for k in ("status", "result", "report_path", "error_code", "trace_meta", "evidence_paths")},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def register_roadmap_seed_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("roadmap-seed", help="Seed a minimal valid roadmap under workspace .cache/index.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--out", default=".cache/index/roadmap.v1.json", help="Output JSON path.")
    ap.add_argument("--title", default="Workspace Roadmap (seed)", help="Seed milestone title.")
    ap.add_argument("--force", default="false", help="Overwrite if output exists (true|false).")
    ap.set_defaults(func=cmd_roadmap_seed)
