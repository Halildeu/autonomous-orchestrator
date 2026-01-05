import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_pack_manifests(core_root: Path, workspace_root: Path | None) -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = []
    core_dir = core_root / "packs"
    if core_dir.exists():
        for p in sorted(core_dir.rglob("pack.manifest.v1.json")):
            if p.is_file():
                paths.append((p, "core"))
    if workspace_root:
        ws_dir = workspace_root / "packs"
        if ws_dir.exists():
            for p in sorted(ws_dir.rglob("pack.manifest.v1.json")):
                if p.is_file():
                    paths.append((p, "workspace"))
    return paths


def _resolve_ref(path_str: str, core_root: Path, workspace_root: Path | None) -> Path | None:
    rel = Path(path_str)
    if workspace_root:
        ws_path = workspace_root / rel
        if ws_path.exists():
            return ws_path
    core_path = core_root / rel
    if core_path.exists():
        return core_path
    return None


def _extract_capability_id(ref_path: Path) -> str | None:
    try:
        obj = _load_json(ref_path)
    except Exception:
        return None
    meta = obj.get("meta") if isinstance(obj, dict) else None
    if isinstance(meta, dict) and isinstance(meta.get("id"), str):
        return meta["id"]
    return None


def _extract_format_meta(ref_path: Path) -> tuple[str | None, str | None]:
    try:
        obj = _load_json(ref_path)
    except Exception:
        return (None, None)
    if not isinstance(obj, dict):
        return (None, None)
    fmt_id = obj.get("id") if isinstance(obj.get("id"), str) else None
    fmt_version = obj.get("version") if isinstance(obj.get("version"), str) else None
    return (fmt_id, fmt_version)


def _parse_manifest(manifest: dict) -> tuple[list[str], list[str], list[str], list[str], list[str], str]:
    provides = manifest.get("provides") if isinstance(manifest, dict) else None
    if not isinstance(provides, dict):
        return ([], [], [], [], [], "")
    intents = [i for i in provides.get("intents", []) if isinstance(i, str)]
    workflows = [w for w in provides.get("workflows", []) if isinstance(w, str)]
    formats = [f for f in provides.get("formats", []) if isinstance(f, str)]
    cap_refs = [c for c in provides.get("capability_refs", []) if isinstance(c, str)]
    fmt_refs = [f for f in provides.get("format_refs", []) if isinstance(f, str)]
    namespace_prefix = manifest.get("namespace_prefix") if isinstance(manifest, dict) else ""
    namespace = namespace_prefix if isinstance(namespace_prefix, str) else ""
    return (intents, workflows, formats, cap_refs, fmt_refs, namespace)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    core_root = Path(__file__).resolve().parents[1]
    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else None

    schema_path = core_root / "schemas" / "pack-manifest.schema.v1.json"
    if not schema_path.exists():
        raise SystemExit("Missing schema: schemas/pack-manifest.schema.v1.json")

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    manifests = _iter_pack_manifests(core_root, workspace_root)
    if not manifests:
        report = {
            "version": "v1",
            "status": "OK",
            "packs_scanned": 0,
            "hard_conflicts": [],
            "soft_conflicts": [],
            "warnings": ["NO_PACKS_FOUND"],
            "hashes": {"pack_list_sha256": _sha256_bytes(b"")},
        }
        out_path = Path(args.out) if args.out else None
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    warnings: list[dict] = []
    hard_conflicts: list[dict] = []
    soft_conflicts: list[dict] = []
    pack_records: dict[str, dict] = {}
    pack_manifest_sha256_map: dict[str, str] = {}

    source_priority = {"core": 0, "workspace": 1}

    for path, source in manifests:
        data = path.read_bytes()
        sha = _sha256_bytes(data)
        manifest = _load_json(path)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: e.json_path)
        if errors:
            hard_conflicts.append(
                {
                    "kind": "SCHEMA_INVALID",
                    "path": path.as_posix(),
                    "errors": [e.message for e in errors[:5]],
                }
            )
            continue

        pack_id = manifest.get("pack_id")
        if not isinstance(pack_id, str):
            hard_conflicts.append({"kind": "MISSING_PACK_ID", "path": path.as_posix()})
            continue

        intents, workflows, formats, cap_refs, fmt_refs, namespace = _parse_manifest(manifest)

        record = {
            "pack_id": pack_id,
            "version": manifest.get("version"),
            "lifecycle_state": manifest.get("lifecycle_state"),
            "namespace_prefix": namespace,
            "intents": intents,
            "workflows": workflows,
            "formats": formats,
            "capability_refs": cap_refs,
            "format_refs": fmt_refs,
            "source": source,
            "path": path.as_posix(),
        }

        if pack_id in pack_records:
            prev = pack_records[pack_id]
            warnings.append(
                {
                    "kind": "DUPLICATE_PACK_ID",
                    "pack_id": pack_id,
                    "paths": sorted({prev.get("path", ""), path.as_posix()}),
                }
            )
            if source_priority[source] >= source_priority.get(prev.get("source", "core"), 0):
                pack_records[pack_id] = record
        else:
            pack_records[pack_id] = record

        pack_manifest_sha256_map[pack_id] = sha

    capability_owner: dict[str, list[str]] = {}
    intent_map: dict[str, dict[str, list[str]]] = {}
    format_owner: dict[str, list[str]] = {}
    format_versions: dict[str, list[str]] = {}

    for pack_id in sorted(pack_records):
        record = pack_records[pack_id]
        namespace = record.get("namespace_prefix") or ""
        cap_ids: list[str] = []
        for cref in record.get("capability_refs", []):
            ref_path = _resolve_ref(cref, core_root, workspace_root)
            if not ref_path:
                warnings.append({"kind": "MISSING_CAPABILITY_REF", "pack_id": pack_id, "ref": cref})
                continue
            cap_id = _extract_capability_id(ref_path)
            if not cap_id:
                warnings.append({"kind": "INVALID_CAPABILITY_REF", "pack_id": pack_id, "ref": cref})
                continue
            cap_ids.append(cap_id)
            if namespace and not cap_id.startswith(namespace):
                hard_conflicts.append(
                    {
                        "kind": "NAMESPACE_PREFIX_MISMATCH",
                        "pack_id": pack_id,
                        "capability_id": cap_id,
                        "namespace_prefix": namespace,
                    }
                )
            capability_owner.setdefault(cap_id, []).append(pack_id)

        fmt_ids: list[str] = []
        for fref in record.get("format_refs", []):
            ref_path = _resolve_ref(fref, core_root, workspace_root)
            if not ref_path:
                warnings.append({"kind": "MISSING_FORMAT_REF", "pack_id": pack_id, "ref": fref})
                continue
            fmt_id, fmt_version = _extract_format_meta(ref_path)
            if not fmt_id:
                warnings.append({"kind": "INVALID_FORMAT_REF", "pack_id": pack_id, "ref": fref})
                continue
            fmt_ids.append(fmt_id)
            format_owner.setdefault(fmt_id, []).append(pack_id)
            if fmt_version:
                format_versions.setdefault(fmt_id, []).append(fmt_version)

        record["capability_ids"] = sorted(set(cap_ids))
        record["format_ids"] = sorted(set(fmt_ids))

        workflows = sorted(set(record.get("workflows", [])))
        workflow_key = ",".join(workflows)
        for intent in record.get("intents", []):
            intent_map.setdefault(intent, {}).setdefault(workflow_key, []).append(pack_id)

    for cap_id, packs in sorted(capability_owner.items()):
        if len(set(packs)) > 1:
            hard_conflicts.append(
                {
                    "kind": "CAPABILITY_ID_CONFLICT",
                    "capability_id": cap_id,
                    "packs": sorted(set(packs)),
                }
            )

    for intent, workflows_map in sorted(intent_map.items()):
        workflow_keys = sorted(k for k in workflows_map.keys() if k)
        if len(workflow_keys) > 1:
            hard_conflicts.append(
                {
                    "kind": "INTENT_WORKFLOW_CONFLICT",
                    "intent": intent,
                    "workflows": workflow_keys,
                    "packs": sorted({p for packs in workflows_map.values() for p in packs}),
                }
            )

    for fmt_id, packs in sorted(format_owner.items()):
        unique = sorted(set(packs))
        if len(unique) > 1:
            versions = sorted({v for v in format_versions.get(fmt_id, []) if isinstance(v, str) and v})
            if len(versions) > 1:
                hard_conflicts.append(
                    {
                        "kind": "FORMAT_VERSION_CONFLICT",
                        "format_id": fmt_id,
                        "versions": versions,
                        "packs": unique,
                    }
                )
            else:
                soft_conflicts.append(
                    {
                        "kind": "FORMAT_ID_CONFLICT",
                        "format_id": fmt_id,
                        "packs": unique,
                        "tie_break": min(unique),
                    }
                )

    pack_list_sha = _sha256_bytes(
        "\n".join(f"{pid}:{pack_manifest_sha256_map.get(pid, '')}" for pid in sorted(pack_records)).encode("utf-8")
    )

    status = "OK"
    if hard_conflicts:
        status = "FAIL"
    elif warnings or soft_conflicts:
        status = "WARN"

    report = {
        "version": "v1",
        "status": status,
        "packs_scanned": len(pack_records),
        "hard_conflicts": hard_conflicts,
        "soft_conflicts": soft_conflicts,
        "warnings": warnings,
        "hashes": {
            "pack_list_sha256": pack_list_sha,
            "pack_manifest_sha256_map": pack_manifest_sha256_map,
        },
    }

    out_path = Path(args.out) if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))

    if status == "FAIL":
        raise SystemExit("Pack manifest conflicts detected (hard fail).")


if __name__ == "__main__":
    main()
