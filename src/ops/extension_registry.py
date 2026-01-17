from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ExtensionRegistryPolicy:
    enabled_by_default: bool
    layer_contract: dict[str, Any]
    entrypoints: dict[str, list[str]]
    determinism: dict[str, bool]
    idle_on_missing_manifests: bool


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_obj(obj: Any) -> str:
    return sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(v) for v in value if isinstance(v, str) and v]
    return sorted(set(cleaned))


def _normalize_entrypoints(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {"ops": [], "kernel_api_actions": [], "cockpit_sections": []}
    return {
        "ops": _list_str(value.get("ops")),
        "kernel_api_actions": _list_str(value.get("kernel_api_actions")),
        "cockpit_sections": _list_str(value.get("cockpit_sections")),
    }


def _normalize_layer_contract(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    write_roots = _list_str(value.get("write_roots_allowlist"))
    if not write_roots:
        write_roots = _list_str(fallback.get("write_roots_allowlist"))
    read_roots = _list_str(value.get("read_roots_allowlist"))
    if not read_roots:
        read_roots = _list_str(fallback.get("read_roots_allowlist"))
    notes = _list_str(value.get("notes"))
    return {
        "write_roots_allowlist": write_roots,
        "read_roots_allowlist": read_roots,
        "notes": notes,
    }


def _normalize_compat(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    return {
        "core_min": str(value.get("core_min", "0.0.0")),
        "core_max": str(value.get("core_max", "")),
        "notes": _list_str(value.get("notes")),
    }


def _load_policy(core_root: Path, workspace_root: Path) -> ExtensionRegistryPolicy:
    defaults = ExtensionRegistryPolicy(
        enabled_by_default=False,
        layer_contract={
            "write_roots_allowlist": [".cache/", "incubator/", "external_allowlist/"],
            "read_roots_allowlist": ["roadmaps/PROJECTS/", "extensions/"],
            "notes": [],
        },
        entrypoints={"ops": ["extension-registry"], "kernel_api_actions": [], "cockpit_sections": ["extensions"]},
        determinism={
            "stable_sort": True,
            "content_hash_required": True,
            "version_required": True,
        },
        idle_on_missing_manifests=True,
    )

    ws_policy = workspace_root / "policies" / "policy_extension_registry.v1.json"
    core_policy = core_root / "policies" / "policy_extension_registry.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled_by_default = bool(obj.get("enabled_by_default", defaults.enabled_by_default))
    layer_contract = _normalize_layer_contract(obj.get("layer_contract"), defaults.layer_contract)
    entrypoints = _normalize_entrypoints(obj.get("entrypoints"))
    determinism_obj = obj.get("determinism") if isinstance(obj.get("determinism"), dict) else {}
    determinism = {
        "stable_sort": bool(determinism_obj.get("stable_sort", defaults.determinism["stable_sort"])),
        "content_hash_required": bool(
            determinism_obj.get("content_hash_required", defaults.determinism["content_hash_required"])
        ),
        "version_required": bool(
            determinism_obj.get("version_required", defaults.determinism["version_required"])
        ),
    }
    idle_on_missing_manifests = bool(
        obj.get("idle_on_missing_manifests", defaults.idle_on_missing_manifests)
    )

    return ExtensionRegistryPolicy(
        enabled_by_default=enabled_by_default,
        layer_contract=layer_contract,
        entrypoints=entrypoints,
        determinism=determinism,
        idle_on_missing_manifests=idle_on_missing_manifests,
    )


def _manifest_validator(core_root: Path) -> Draft202012Validator | None:
    schema_path = core_root / "schemas" / "extension-manifest.schema.v1.json"
    if not schema_path.exists():
        return None
    try:
        schema = _load_json(schema_path)
    except Exception:
        return None
    try:
        Draft202012Validator.check_schema(schema)
    except Exception:
        return None
    return Draft202012Validator(schema)


def _validate_manifest(validator: Draft202012Validator | None, manifest: dict[str, Any]) -> list[str]:
    if validator is None:
        return ["SCHEMA_MISSING"]
    errors = sorted(validator.iter_errors(manifest), key=lambda e: e.json_path)
    return [f"{e.json_path or '$'}: {e.message}" for e in errors[:10]]


def _entry_from_manifest(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    policy: ExtensionRegistryPolicy,
    content_hash: str,
    source_type: str,
) -> dict[str, Any]:
    layer_contract = _normalize_layer_contract(manifest.get("layer_contract"), policy.layer_contract)
    entrypoints = _normalize_entrypoints(manifest.get("entrypoints"))
    return {
        "extension_id": str(manifest.get("extension_id")),
        "semver": str(manifest.get("semver")),
        "origin": str(manifest.get("origin")),
        "owner": str(manifest.get("owner")),
        "owner_tenant": str(manifest.get("owner_tenant")) if isinstance(manifest.get("owner_tenant"), str) else "",
        "source_type": source_type,
        "manifest_path": manifest_path.as_posix(),
        "layer_contract": layer_contract,
        "entrypoints": entrypoints,
        "policies": _list_str(manifest.get("policies")),
        "ui_surfaces": _list_str(manifest.get("ui_surfaces")),
        "compat": _normalize_compat(manifest.get("compat")),
        "content_hash": content_hash,
        "enabled": bool(manifest.get("enabled", policy.enabled_by_default)),
    }


def _entry_from_project_manifest(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    policy: ExtensionRegistryPolicy,
    content_hash: str,
) -> dict[str, Any]:
    project_id = manifest.get("project_id") if isinstance(manifest.get("project_id"), str) else None
    ext_id = project_id.strip() if project_id else manifest_path.parent.name
    semver = manifest.get("version") if isinstance(manifest.get("version"), str) else "0.0.0"
    return {
        "extension_id": str(ext_id),
        "semver": str(semver),
        "origin": "CORE",
        "owner": "CORE",
        "owner_tenant": "",
        "source_type": "project_manifest",
        "manifest_path": manifest_path.as_posix(),
        "layer_contract": _normalize_layer_contract({}, policy.layer_contract),
        "entrypoints": _normalize_entrypoints({}),
        "policies": [],
        "ui_surfaces": [],
        "compat": _normalize_compat({}),
        "content_hash": content_hash,
        "enabled": bool(policy.enabled_by_default),
    }


def _discover_manifests(core_root: Path) -> tuple[list[Path], list[Path]]:
    ext_paths: list[Path] = []

    extensions_root = core_root / "extensions"
    if extensions_root.exists():
        ext_paths.extend(extensions_root.rglob("extension.manifest.v1.json"))

    return (sorted(ext_paths), [])


def build_extension_registry(*, workspace_root: Path, mode: str = "report") -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    validator = _manifest_validator(core_root)

    ext_paths, proj_paths = _discover_manifests(core_root)
    ext_by_dir = {p.parent: p for p in ext_paths}
    proj_by_dir = {p.parent: p for p in proj_paths}
    all_dirs = sorted(set(ext_by_dir.keys()) | set(proj_by_dir.keys()), key=lambda p: p.as_posix())

    errors: list[str] = []
    notes: list[str] = []
    entries: list[dict[str, Any]] = []
    for proj_dir in all_dirs:
        if proj_dir not in ext_by_dir:
            continue
        manifest_path = ext_by_dir[proj_dir]
        try:
            manifest_obj = _load_json(manifest_path)
        except Exception:
            errors.append(f"{manifest_path.as_posix()}: invalid_json")
            continue
        if not isinstance(manifest_obj, dict):
            errors.append(f"{manifest_path.as_posix()}: invalid_object")
            continue
        validation_errors = _validate_manifest(validator, manifest_obj)
        if validation_errors:
            errors.append(f"{manifest_path.as_posix()}: schema_invalid")
            errors.extend([f"{manifest_path.as_posix()} {e}" for e in validation_errors])
            continue
        content_hash = _hash_obj(manifest_obj)
        entries.append(
            _entry_from_manifest(
                manifest=manifest_obj,
                manifest_path=manifest_path.relative_to(core_root),
                policy=policy,
                content_hash=content_hash,
                source_type="extension_manifest",
            )
        )

    if entries:
        entries.sort(key=lambda x: (str(x.get("extension_id") or ""), str(x.get("manifest_path") or "")))
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in entries:
            ext_id = str(entry.get("extension_id") or "")
            if not ext_id:
                continue
            if ext_id in seen:
                continue
            seen.add(ext_id)
            deduped.append(entry)
        if len(deduped) != len(entries):
            notes.append("duplicate_extension_id_deduped")
        entries = deduped

    if policy.determinism.get("stable_sort", True):
        entries.sort(key=lambda x: (str(x.get("extension_id") or ""), str(x.get("semver") or "")))

    enabled_count = len([e for e in entries if e.get("enabled") is True])
    counts = {"total": len(entries), "enabled": enabled_count}

    cursor_payload = [
        {"extension_id": e.get("extension_id"), "content_hash": e.get("content_hash")}
        for e in entries
    ]
    registry_cursor = _hash_obj(cursor_payload)
    content_hash = _hash_obj(entries)

    status = "OK"
    error_code = None
    next_steps: list[str] = []
    if not entries:
        if policy.idle_on_missing_manifests:
            status = "IDLE"
            error_code = "NO_MANIFESTS_FOUND"
            next_steps = [
                "Auto-create stub manifests",
                "Add extension.manifest.v1.json under extensions/",
                "Durumu goster",
            ]
        else:
            status = "WARN"
    elif errors:
        status = "FAIL" if mode == "strict" else "WARN"

    payload = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": status,
        "error_code": error_code,
        "registry_cursor": registry_cursor,
        "content_hash": content_hash,
        "counts": counts,
        "extensions": entries,
        "next_steps": next_steps,
        "notes": notes,
        "errors": errors,
    }

    out_index = workspace_root / ".cache" / "index" / "extension_registry.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "extension_registry_summary.v1.md"
    out_index.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_index.write_text(_dump_json(payload), encoding="utf-8")

    md_lines = [
        "# Extension Registry Summary (v1)",
        "",
        f"Status: {status}",
        f"Total: {counts['total']}",
        f"Enabled: {counts['enabled']}",
        f"Registry: {out_index.relative_to(workspace_root)}",
    ]
    if notes:
        md_lines.append("Notes: " + ", ".join(notes))
    if entries:
        md_lines.append("")
        md_lines.append("## Top Extensions")
        for e in entries[:5]:
            md_lines.append(f"- {e.get('extension_id')} {e.get('semver')}")
    if errors:
        md_lines.append("")
        md_lines.append("## Errors")
        for err in errors[:10]:
            md_lines.append(f"- {err}")

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "error_code": error_code,
        "registry_path": str(out_index.relative_to(workspace_root)),
        "summary_path": str(out_md.relative_to(workspace_root)),
        "counts": counts,
        "notes": notes,
        "next_steps": next_steps,
    }


def run_extension_registry(*, workspace_root: Path, mode: str, chat: bool) -> dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in {"report", "strict"}:
        return {"status": "FAIL", "error_code": "INVALID_MODE"}

    result = build_extension_registry(workspace_root=workspace_root, mode=mode)
    status = result.get("status") if isinstance(result, dict) else "WARN"

    if chat:
        preview_lines = [
            "PROGRAM-LED: extension-registry; user_command=false",
            f"workspace_root={workspace_root}",
            f"mode={mode}",
        ]
        result_lines = [
            f"status={status}",
            f"count_total={result.get('counts', {}).get('total', 0)}",
            f"enabled_count={result.get('counts', {}).get('enabled', 0)}",
        ]
        if result.get("error_code"):
            result_lines.append(f"error_code={result.get('error_code')}")
        evidence_lines = [
            f"extension_registry={result.get('registry_path')}",
            f"summary={result.get('summary_path')}",
        ]
        actions_line = "no_actions"
        next_lines = result.get("next_steps") if isinstance(result.get("next_steps"), list) else []
        if not next_lines:
            next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join([str(x) for x in evidence_lines if x]))
        print("ACTIONS:")
        print(actions_line)
        print("NEXT:")
        print("\n".join(str(x) for x in next_lines))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))

    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.extension_registry")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--mode", default="report", help="report|strict (default: report)")
    ap.add_argument("--chat", default="false", help="true|false (default: false)")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    chat = str(args.chat).strip().lower() in {"1", "true", "yes", "y", "on"}
    res = run_extension_registry(workspace_root=workspace_root, mode=str(args.mode), chat=chat)
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
