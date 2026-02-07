from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    try:
        target.relative_to(workspace_root)
    except Exception as e:
        raise ValueError(f"Path escapes workspace_root: {target}") from e


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def put(*, workspace_root: Path, relpath: str) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    rel = Path(relpath).as_posix()
    src = (workspace_root / rel).resolve()
    _ensure_inside_workspace(workspace_root, src)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Artifact source not found: {rel}")

    data = src.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    stored_rel = Path(".cache") / "artifacts" / f"{sha}.bin"
    stored_path = (workspace_root / stored_rel).resolve()
    _ensure_inside_workspace(workspace_root, stored_path)

    stored_path.parent.mkdir(parents=True, exist_ok=True)
    if not stored_path.exists():
        tmp = stored_path.with_name(stored_path.name + f".tmp.{os.getpid()}")
        tmp.write_bytes(data)
        tmp.replace(stored_path)

    pointer = {
        "version": "v1",
        "sha256": sha,
        "size_bytes": len(data),
        "stored_path": stored_rel.as_posix(),
        "original_relpath": rel,
        "created_at": _now_iso8601(),
    }
    return pointer


def get(*, workspace_root: Path, pointer: dict[str, Any], out_relpath: str) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    stored_rel = pointer.get("stored_path") if isinstance(pointer, dict) else None
    if not isinstance(stored_rel, str) or not stored_rel.strip():
        raise ValueError("Pointer missing stored_path")

    stored_path = (workspace_root / Path(stored_rel).as_posix()).resolve()
    _ensure_inside_workspace(workspace_root, stored_path)
    if not stored_path.exists() or not stored_path.is_file():
        raise FileNotFoundError(f"Stored artifact missing: {stored_rel}")

    out_rel = Path(out_relpath).as_posix()
    out_path = (workspace_root / out_rel).resolve()
    _ensure_inside_workspace(workspace_root, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(stored_path.read_bytes())

    return {
        "status": "OK",
        "stored_path": stored_rel,
        "out_path": out_rel,
        "bytes": out_path.stat().st_size,
    }


def write_pointer(path: Path, pointer: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(_dump_json(pointer), encoding="utf-8")
    tmp.replace(path)
