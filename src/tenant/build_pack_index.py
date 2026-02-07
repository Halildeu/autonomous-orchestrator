import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(path_str: str, core_root: Path, workspace_root: Path) -> Path | None:
    rel = Path(path_str)
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


def _extract_format_id(ref_path: Path) -> str | None:
    try:
        obj = _load_json(ref_path)
    except Exception:
        return None
    if isinstance(obj, dict) and isinstance(obj.get("id"), str):
        return obj["id"]
    return None


def _collect_manifests(core_root: Path, workspace_root: Path) -> list[tuple[Path, str]]:
    manifests: list[tuple[Path, str]] = []
    core_dir = core_root / "packs"
    if core_dir.exists():
        for p in sorted(core_dir.rglob("pack.manifest.v1.json")):
            if p.is_file():
                manifests.append((p, "core"))
    ws_dir = workspace_root / "packs"
    if ws_dir.exists():
        for p in sorted(ws_dir.rglob("pack.manifest.v1.json")):
            if p.is_file():
                manifests.append((p, "workspace"))
    return manifests


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args()

    dry_run = str(args.dry_run).lower() == "true"
    workspace_root = Path(args.workspace_root).resolve()
    core_root = Path(__file__).resolve().parents[2]

    schema_path = core_root / "schemas" / "pack-manifest.schema.v1.json"
    if not schema_path.exists():
        raise SystemExit("Missing schema: schemas/pack-manifest.schema.v1.json")

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    index_dir = workspace_root / ".cache" / "index"
    index_path = index_dir / "pack_capability_index.v1.json"
    cursor_path = index_dir / "pack_index_cursor.v1.json"

    prev_by_id: dict[str, dict] = {}
    if index_path.exists():
        try:
            prev_obj = _load_json(index_path)
            prev_packs = prev_obj.get("packs") if isinstance(prev_obj, dict) else None
            if isinstance(prev_packs, list):
                for p in prev_packs:
                    if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                        prev_by_id[p["pack_id"]] = p
        except Exception:
            prev_by_id = {}

    prev_cursor = {}
    if cursor_path.exists():
        try:
            prev_cursor = _load_json(cursor_path)
        except Exception:
            prev_cursor = {}

    prev_sha_map = prev_cursor.get("pack_manifest_sha256_map") if isinstance(prev_cursor, dict) else {}
    if not isinstance(prev_sha_map, dict):
        prev_sha_map = {}

    pack_records: dict[str, dict] = {}
    pack_manifest_sha256_map: dict[str, str] = {}
    warnings: list[dict] = []
    hard_conflicts: list[dict] = []
    soft_conflicts: list[dict] = []
    source_priority = {"core": 0, "workspace": 1}

    for path, source in _collect_manifests(core_root, workspace_root):
        data = path.read_bytes()
        sha = _sha256_bytes(data)
        manifest = _load_json(path)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: e.json_path)
        if errors:
            raise SystemExit(f"Invalid pack manifest: {path}")
        pack_id = manifest.get("pack_id")
        if not isinstance(pack_id, str):
            raise SystemExit(f"Missing pack_id: {path}")
        pack_manifest_sha256_map[pack_id] = sha

        if pack_id in pack_records:
            prev = pack_records[pack_id]
            warnings.append(
                {
                    "kind": "DUPLICATE_PACK_ID",
                    "pack_id": pack_id,
                    "paths": sorted({prev.get("path", ""), path.as_posix()}),
                }
            )
            if source_priority[source] < source_priority.get(prev.get("source", "core"), 0):
                continue

        if (
            pack_id in prev_by_id
            and isinstance(prev_sha_map, dict)
            and prev_sha_map.get(pack_id) == sha
        ):
            record = dict(prev_by_id[pack_id])
            record["source"] = source
            record["path"] = path.as_posix()
            pack_records[pack_id] = record
            continue

        provides = manifest.get("provides") if isinstance(manifest, dict) else {}
        intents = [i for i in provides.get("intents", []) if isinstance(i, str)] if isinstance(provides, dict) else []
        workflows = [w for w in provides.get("workflows", []) if isinstance(w, str)] if isinstance(provides, dict) else []
        formats = [f for f in provides.get("formats", []) if isinstance(f, str)] if isinstance(provides, dict) else []
        cap_refs = [c for c in provides.get("capability_refs", []) if isinstance(c, str)] if isinstance(provides, dict) else []
        fmt_refs = [f for f in provides.get("format_refs", []) if isinstance(f, str)] if isinstance(provides, dict) else []
        namespace = manifest.get("namespace_prefix") if isinstance(manifest.get("namespace_prefix"), str) else ""

        cap_ids: list[str] = []
        for cref in cap_refs:
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

        fmt_ids: list[str] = []
        for fref in fmt_refs:
            ref_path = _resolve_ref(fref, core_root, workspace_root)
            if not ref_path:
                warnings.append({"kind": "MISSING_FORMAT_REF", "pack_id": pack_id, "ref": fref})
                continue
            fmt_id = _extract_format_id(ref_path)
            if not fmt_id:
                warnings.append({"kind": "INVALID_FORMAT_REF", "pack_id": pack_id, "ref": fref})
                continue
            fmt_ids.append(fmt_id)

        record = {
            "pack_id": pack_id,
            "version": manifest.get("version"),
            "lifecycle_state": manifest.get("lifecycle_state"),
            "namespace_prefix": namespace,
            "intents": intents,
            "workflows": workflows,
            "formats": formats,
            "capability_ids": sorted(set(cap_ids)),
            "format_ids": sorted(set(fmt_ids)),
            "iso_kernel_refs": manifest.get("iso_kernel_refs", {}),
            "source": source,
            "path": path.as_posix(),
        }
        pack_records[pack_id] = record

    capability_owner: dict[str, list[str]] = {}
    intent_map: dict[str, dict[str, list[str]]] = {}
    format_owner: dict[str, list[str]] = {}

    for pack_id in sorted(pack_records):
        record = pack_records[pack_id]
        for cap_id in record.get("capability_ids", []):
            if isinstance(cap_id, str):
                capability_owner.setdefault(cap_id, []).append(pack_id)
        workflows = sorted(set(record.get("workflows", [])))
        workflow_key = ",".join(workflows)
        for intent in record.get("intents", []):
            if isinstance(intent, str):
                intent_map.setdefault(intent, {}).setdefault(workflow_key, []).append(pack_id)
        for fmt_id in record.get("format_ids", []):
            if isinstance(fmt_id, str):
                format_owner.setdefault(fmt_id, []).append(pack_id)

    for cap_id, packs in sorted(capability_owner.items()):
        if len(set(packs)) > 1:
            hard_conflicts.append(
                {"kind": "CAPABILITY_ID_CONFLICT", "capability_id": cap_id, "packs": sorted(set(packs))}
            )

    for intent, workflows_map in sorted(intent_map.items()):
        keys = sorted(k for k in workflows_map.keys() if k)
        if len(keys) > 1:
            hard_conflicts.append(
                {
                    "kind": "INTENT_WORKFLOW_CONFLICT",
                    "intent": intent,
                    "workflows": keys,
                    "packs": sorted({p for packs in workflows_map.values() for p in packs}),
                }
            )

    for fmt_id, packs in sorted(format_owner.items()):
        unique = sorted(set(packs))
        if len(unique) > 1:
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

    index_obj = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "packs": [pack_records[pid] for pid in sorted(pack_records)],
        "hard_conflicts": hard_conflicts,
        "soft_conflicts": soft_conflicts,
        "hashes": {"index_sha256": "", "pack_list_sha256": pack_list_sha},
    }

    index_bytes = json.dumps(index_obj, indent=2, sort_keys=True).encode("utf-8")
    index_sha = _sha256_bytes(index_bytes)
    index_obj["hashes"]["index_sha256"] = index_sha

    if dry_run:
        print(
            json.dumps(
                {
                    "status": "WOULD_WRITE",
                    "out": str(index_path),
                    "packs_found": len(pack_records),
                    "hard_conflicts": len(hard_conflicts),
                    "soft_conflicts": len(soft_conflicts),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    index_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cursor_obj = {
        "version": "v1",
        "last_pack_list_sha256": pack_list_sha,
        "pack_manifest_sha256_map": pack_manifest_sha256_map,
        "last_index_sha256": index_sha,
    }
    cursor_path.write_text(json.dumps(cursor_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "OK" if status != "FAIL" else "FAIL",
                "out": str(index_path),
                "packs_found": len(pack_records),
                "hard_conflicts": len(hard_conflicts),
                "soft_conflicts": len(soft_conflicts),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if status == "FAIL":
        raise SystemExit("Pack index hard conflicts detected.")


if __name__ == "__main__":
    main()
