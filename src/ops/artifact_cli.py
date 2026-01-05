from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.artifacts import store


def _resolve_under_workspace(workspace_root: Path, relpath: str) -> Path:
    workspace_root = workspace_root.resolve()
    rel = Path(relpath).as_posix()
    p = (workspace_root / rel).resolve()
    try:
        p.relative_to(workspace_root)
    except Exception as e:
        raise ValueError(f"Path escapes workspace_root: {rel}") from e
    return p


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_artifact_put(args: argparse.Namespace) -> int:
    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    relpath = str(args.path)
    try:
        pointer = store.put(workspace_root=workspace_root, relpath=relpath)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "ARTIFACT_PUT_FAIL", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    out_rel = str(args.out)
    try:
        out_path = _resolve_under_workspace(workspace_root, out_rel)
        store.write_pointer(out_path, pointer)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "POINTER_WRITE_FAIL", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "pointer_path": Path(out_rel).as_posix(),
        "sha256": pointer.get("sha256"),
        "stored_path": pointer.get("stored_path"),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_artifact_get(args: argparse.Namespace) -> int:
    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        pointer_path = _resolve_under_workspace(workspace_root, str(args.pointer))
        pointer = _load_json(pointer_path)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "POINTER_READ_FAIL", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        res = store.get(workspace_root=workspace_root, pointer=pointer, out_relpath=str(args.out))
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error_code": "ARTIFACT_GET_FAIL", "message": str(e)[:300]}, ensure_ascii=False, sort_keys=True))
        return 2

    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0


def register_artifact_subcommands(sub: argparse._SubParsersAction) -> None:
    ap_put = sub.add_parser("artifact-put", help="Store an artifact under workspace .cache/artifacts and write a pointer JSON.")
    ap_put.add_argument("--workspace-root", required=True)
    ap_put.add_argument("--path", required=True, help="Relative path to the artifact under workspace-root.")
    ap_put.add_argument("--out", required=True, help="Pointer JSON output path (relative to workspace-root).")
    ap_put.set_defaults(func=cmd_artifact_put)

    ap_get = sub.add_parser("artifact-get", help="Restore an artifact from a pointer JSON.")
    ap_get.add_argument("--workspace-root", required=True)
    ap_get.add_argument("--pointer", required=True, help="Pointer JSON path (relative to workspace-root).")
    ap_get.add_argument("--out", required=True, help="Output path (relative to workspace-root).")
    ap_get.set_defaults(func=cmd_artifact_get)
