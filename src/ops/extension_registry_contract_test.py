from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.extension_registry import build_extension_registry, _discover_manifests

    ws = repo_root / ".cache" / "ws_extension_registry_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res1 = build_extension_registry(workspace_root=ws, mode="report")
    if res1.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("extension_registry_contract_test failed: invalid status.")

    reg_path = ws / ".cache" / "index" / "extension_registry.v1.json"
    if not reg_path.exists():
        raise SystemExit("extension_registry_contract_test failed: registry path missing.")

    schema_path = repo_root / "schemas" / "extension-registry.schema.v1.json"
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(_load_json(reg_path))

    res2 = build_extension_registry(workspace_root=ws, mode="report")
    if res1.get("registry_path") != res2.get("registry_path"):
        raise SystemExit("extension_registry_contract_test failed: registry path mismatch.")

    reg_obj_1 = _load_json(reg_path)
    reg_obj_2 = _load_json(reg_path)
    if reg_obj_1.get("content_hash") != reg_obj_2.get("content_hash"):
        raise SystemExit("extension_registry_contract_test failed: content_hash not stable.")

    extensions = reg_obj_1.get("extensions") if isinstance(reg_obj_1, dict) else None
    entries = [e for e in extensions if isinstance(e, dict)] if isinstance(extensions, list) else []
    for entry in entries:
        manifest_path = entry.get("manifest_path")
        if not isinstance(manifest_path, str) or not manifest_path:
            continue
        manifest_file = repo_root / manifest_path
        if not manifest_file.exists():
            raise SystemExit("extension_registry_contract_test failed: manifest path missing.")
        manifest = _load_json(manifest_file)
        docs_ref = manifest.get("docs_ref") if isinstance(manifest.get("docs_ref"), str) else ""
        extension_id = manifest.get("extension_id") if isinstance(manifest.get("extension_id"), str) else ""
        if docs_ref:
            if not docs_ref.startswith("docs/OPERATIONS/EXTENSIONS.md#ext-"):
                raise SystemExit("extension_registry_contract_test failed: docs_ref anchor invalid.")
            if extension_id and docs_ref.split("#", 1)[-1] != f"ext-{extension_id}":
                raise SystemExit("extension_registry_contract_test failed: docs_ref does not match extension_id.")
        ai_refs = manifest.get("ai_context_refs") if isinstance(manifest.get("ai_context_refs"), list) else []
        for ref in ai_refs:
            if not isinstance(ref, str) or not ref:
                raise SystemExit("extension_registry_contract_test failed: ai_context_refs invalid entry.")
            if "://" in ref or ref.startswith("http"):
                raise SystemExit("extension_registry_contract_test failed: ai_context_refs must be repo paths.")
        entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
        for key in ["ops", "ops_single_gate", "kernel_api_actions", "cockpit_sections"]:
            vals = entrypoints.get(key) if isinstance(entrypoints.get(key), list) else []
            filtered = [str(x) for x in vals if isinstance(x, str)]
            if filtered != sorted(filtered):
                raise SystemExit("extension_registry_contract_test failed: entrypoints list not sorted.")

    ws_idle = repo_root / ".cache" / "ws_extension_registry_idle"
    if ws_idle.exists():
        shutil.rmtree(ws_idle)
    ws_idle.mkdir(parents=True, exist_ok=True)

    orig_discover = _discover_manifests
    try:
        def _empty_discover(_core_root: Path) -> tuple[list[Path], list[Path]]:
            return ([], [])
        globals_dict = sys.modules["src.ops.extension_registry"].__dict__
        globals_dict["_discover_manifests"] = _empty_discover
        idle_res = build_extension_registry(workspace_root=ws_idle, mode="report")
    finally:
        globals_dict = sys.modules["src.ops.extension_registry"].__dict__
        globals_dict["_discover_manifests"] = orig_discover

    if idle_res.get("status") != "IDLE":
        raise SystemExit("extension_registry_contract_test failed: IDLE semantics not honored.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
