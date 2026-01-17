from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.trace_meta import build_run_id, build_trace_meta
from src.roadmap.state import default_state


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_workspace_root(workspace_arg: str) -> Path | None:
    root = repo_root()
    ws = Path(str(workspace_arg or "").strip())
    if not ws:
        return None
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        return None
    return ws


def _resolve_roadmap_path(workspace_root: Path, roadmap_arg: str | None) -> tuple[Path | None, str | None]:
    root = repo_root().resolve()
    candidate: Path | None = None
    if isinstance(roadmap_arg, str) and roadmap_arg.strip():
        raw = Path(roadmap_arg.strip())
        candidate = (root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    else:
        ws_seed = (workspace_root / ".cache" / "index" / "roadmap.v1.json").resolve()
        if ws_seed.exists():
            candidate = ws_seed
        else:
            root_seed = (root / "roadmap.v1.json").resolve()
            if root_seed.exists():
                candidate = root_seed
    if candidate is None:
        return None, "ROADMAP_PATH_MISSING"
    try:
        candidate.relative_to(root)
    except Exception:
        return None, "ROADMAP_PATH_OUTSIDE_REPO"
    if not candidate.exists() or not candidate.is_file():
        return None, "ROADMAP_PATH_MISSING"
    return candidate, None


def _resolve_state_path(workspace_root: Path, out_arg: str | None) -> Path | None:
    raw = Path(str(out_arg or "").strip()) if out_arg else Path(".cache/roadmap_state.v1.json")
    candidate = raw.resolve() if raw.is_absolute() else (workspace_root / raw).resolve()
    allowed = [
        (workspace_root / ".cache" / "roadmap_state.v1.json").resolve(),
        (workspace_root / ".cache" / "index" / "roadmap_state.v1.json").resolve(),
    ]
    for allowed_path in allowed:
        if candidate == allowed_path:
            return candidate
    return None


def _parse_mode(raw: str | None) -> str | None:
    value = str(raw or "sync").strip().lower()
    if value in {"sync", "reset"}:
        return value
    return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run_roadmap_state_sync(
    *,
    workspace_root: Path,
    roadmap_path: Path | str,
    out_path: Path | str | None = None,
    mode: str = "sync",
) -> dict[str, Any]:
    resolved_mode = _parse_mode(mode)
    if resolved_mode is None:
        return {"status": "FAIL", "error_code": "MODE_INVALID"}

    roadmap_resolved, roadmap_error = _resolve_roadmap_path(workspace_root, str(roadmap_path))
    if roadmap_resolved is None:
        return {"status": "FAIL", "error_code": roadmap_error or "ROADMAP_PATH_INVALID"}

    out_resolved = _resolve_state_path(workspace_root, str(out_path) if out_path is not None else None)
    if out_resolved is None:
        return {"status": "FAIL", "error_code": "OUT_PATH_INVALID"}

    evidence_paths: list[str] = []
    try:
        state_rel = out_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        state_rel = str(out_resolved)
    evidence_paths.append(state_rel)

    try:
        roadmap_rel = roadmap_resolved.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        roadmap_rel = str(roadmap_resolved)
    evidence_paths.append(roadmap_rel)

    inputs = {
        "roadmap_path": str(roadmap_resolved),
        "out_path": str(out_resolved),
        "mode": resolved_mode,
    }
    run_id = build_run_id(workspace_root=workspace_root, op_name="roadmap-state-sync", inputs=inputs)
    trace_meta = build_trace_meta(
        work_item_id=run_id,
        work_item_kind="ROADMAP_STATE_SYNC",
        run_id=run_id,
        policy_hash=None,
        evidence_paths=evidence_paths,
        workspace_root=str(workspace_root),
    )

    roadmap_sha = _sha256_file(roadmap_resolved)
    ws_abs = workspace_root.resolve()
    rm_abs = roadmap_resolved.resolve()

    existing_state = None
    if out_resolved.exists() and resolved_mode == "sync":
        try:
            existing_state = _load_json(out_resolved)
        except Exception:
            existing_state = None
        if not isinstance(existing_state, dict):
            existing_state = None

    base_origin = "default"
    state_obj = default_state(roadmap_path=rm_abs, workspace_root=ws_abs)
    if resolved_mode == "sync" and isinstance(existing_state, dict):
        if (
            existing_state.get("roadmap_path") == str(rm_abs)
            and existing_state.get("workspace_root") == str(ws_abs)
        ):
            state_obj = existing_state
            base_origin = "existing"

    state_obj["roadmap_path"] = str(rm_abs)
    state_obj["workspace_root"] = str(ws_abs)

    if base_origin == "existing":
        old_sha = state_obj.get("roadmap_sha256")
        if isinstance(old_sha, str) and len(old_sha) == 64 and all(c in "0123456789abcdef" for c in old_sha):
            if old_sha != roadmap_sha:
                state_obj["last_roadmap_sha256"] = old_sha
                state_obj["drift_detected"] = True
            else:
                state_obj["drift_detected"] = False
        else:
            state_obj["last_roadmap_sha256"] = None
            state_obj["drift_detected"] = False
    else:
        state_obj["last_roadmap_sha256"] = None
        state_obj["drift_detected"] = False

    state_obj["roadmap_sha256"] = roadmap_sha

    existing_obj = None
    if out_resolved.exists():
        try:
            existing_obj = _load_json(out_resolved)
        except Exception:
            existing_obj = None

    if existing_obj == state_obj:
        result = "ALREADY_DONE"
    else:
        payload = json.dumps(state_obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        _atomic_write_text(out_resolved, payload)
        result = "CREATED" if existing_obj is None else "UPDATED"

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws_abs),
        "status": "OK",
        "result": result,
        "mode": resolved_mode,
        "roadmap_path": str(rm_abs),
        "roadmap_sha256": roadmap_sha,
        "state_path": state_rel,
        "evidence_paths": sorted(set(evidence_paths)),
        "trace_meta": trace_meta,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "WORKSPACE_ONLY=true", "TRAVERSAL_BLOCKED=true"],
    }


def cmd_roadmap_state_sync(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(str(args.workspace_root))
    if ws is None:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    result = run_roadmap_state_sync(
        workspace_root=ws,
        roadmap_path=str(args.roadmap or ""),
        out_path=str(getattr(args, "out", "") or ""),
        mode=str(getattr(args, "mode", "sync") or "sync"),
    )
    status = str(result.get("status") or "")
    if status != "OK":
        warn(f"FAIL error={result.get('error_code')}")
        return 2
    print(
        json.dumps(
            {k: result.get(k) for k in ("status", "result", "state_path", "roadmap_path", "roadmap_sha256", "evidence_paths", "trace_meta")},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def register_roadmap_state_sync_subcommand(parent: argparse._SubParsersAction) -> None:
    ap = parent.add_parser("roadmap-state-sync", help="Sync roadmap state for the given roadmap/workspace.")
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--roadmap", default="", help="Roadmap path (default: workspace seed if present).")
    ap.add_argument("--out", default="", help="State output path (default: .cache/roadmap_state.v1.json).")
    ap.add_argument("--mode", default="sync", help="sync|reset (default: sync).")
    ap.set_defaults(func=cmd_roadmap_state_sync)
