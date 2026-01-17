from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(_dump_json(payload), encoding="utf-8")
    tmp_path.replace(path)


def _load_json(path: Path) -> tuple[dict | None, bool]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, False
    if not isinstance(obj, dict):
        return None, False
    return obj, True


def _file_sha256(path: Path) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    return hashlib.sha256(data).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _pack_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "pack_capability_index.v1.json"


def _pack_index_cursor_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "pack_index_cursor.v1.json"


def _pack_selection_trace_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "pack_selection_trace.v1.json"


def _load_expected_pack_selection_paths(workspace_root: Path) -> list[Path]:
    repo_root = _repo_root()
    report_path = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "pack_selection_trace_expected_paths.v1.json"
    )
    expected: list[str] = []
    if report_path.exists():
        obj, valid = _load_json(report_path)
        if valid and isinstance(obj, dict):
            candidates = obj.get("expected_paths_sorted") or obj.get("expected_paths") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    root = workspace_root.resolve()
    resolved: list[Path] = []
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "pack_selection_trace.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "index" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "pack_selection_trace.v1.json":
            continue
        resolved.append(path)
    canonical = _pack_selection_trace_path(root)
    if not resolved:
        resolved = [canonical]
    elif canonical not in resolved:
        resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _selection_trace_has_expected(obj: dict) -> bool:
    selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
    if not isinstance(selected, list):
        return False
    return any(isinstance(s, str) and s.strip() for s in selected)


def _build_pack_selection_trace(workspace_root: Path) -> dict:
    selected_pack_ids: list[str] = []
    index_path = _pack_index_path(workspace_root)
    if index_path.exists():
        obj, valid = _load_json(index_path)
        if valid and isinstance(obj, dict):
            packs = obj.get("packs") if isinstance(obj, dict) else None
            pack_ids = {
                p.get("pack_id")
                for p in packs
                if isinstance(p, dict) and isinstance(p.get("pack_id"), str)
            } if isinstance(packs, list) else set()
            if pack_ids:
                selected_pack_ids.append(sorted(pack_ids)[0])
    if not selected_pack_ids:
        selected_pack_ids = ["pack-document-management"]
    trace = {
        "version": "v1",
        "kind": "pack_selection_trace",
        "workspace_root": str(workspace_root),
        "created_at": _now_iso(),
        "input": {"intent": "demo", "artifact_type": ""},
        "items": [],
        "shortlist": [{"pack_id": pid, "reason": ["seed"]} for pid in selected_pack_ids],
        "selected_pack_ids": selected_pack_ids,
        "conflicts": {"hard": 0, "soft": 0},
    }
    trace_hash = _sha256_bytes(json.dumps(trace, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    trace["hashes"] = {"trace_sha256": trace_hash}
    return trace


def _pack_advisor_suggestions_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "learning" / "pack_advisor_suggestions.v1.json"


def _load_expected_pack_advisor_paths(workspace_root: Path) -> list[Path]:
    repo_root = _repo_root()
    report_path = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "pack_advisor_suggestions_expected_paths.v0.1.json"
    )
    expected: list[str] = []
    if report_path.exists():
        obj, valid = _load_json(report_path)
        if valid and isinstance(obj, dict):
            candidates = obj.get("expected_paths_sorted") or obj.get("expected_paths") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    root = workspace_root.resolve()
    resolved: list[Path] = []
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "pack_advisor_suggestions.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "learning" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "pack_advisor_suggestions.v1.json":
            continue
        resolved.append(path)
    canonical = _pack_advisor_suggestions_path(root)
    if not resolved:
        resolved = [canonical]
    elif canonical not in resolved:
        resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _pack_advisor_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"version", "generated_at", "workspace_root", "selected_pack_ids", "suggestions", "safety"}
    if not required.issubset(obj.keys()):
        return False
    selected = obj.get("selected_pack_ids")
    if not isinstance(selected, list):
        return False
    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list):
        return False
    safety = obj.get("safety") if isinstance(obj.get("safety"), dict) else None
    status = safety.get("status") if isinstance(safety, dict) else None
    return status in {"OK", "WARN", "FAIL"}


def _load_selected_pack_ids_for_advisor(workspace_root: Path) -> list[str]:
    trace_path = _pack_selection_trace_path(workspace_root)
    if not trace_path.exists():
        return []
    obj, valid = _load_json(trace_path)
    if not valid or not isinstance(obj, dict):
        return []
    selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
    ids = [x for x in selected if isinstance(x, str) and x.strip()] if isinstance(selected, list) else []
    return sorted(set(ids))


def _build_pack_advisor_suggestions(workspace_root: Path) -> dict:
    selected_pack_ids = _load_selected_pack_ids_for_advisor(workspace_root)
    notes: list[str] = []
    if not selected_pack_ids:
        selected_pack_ids = ["pack-document-management"]
        notes.append("PRESEED_SELECTED_PACK_IDS")
    safety_status = "WARN" if notes else "OK"
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "selected_pack_ids": selected_pack_ids,
        "suggestions": [],
        "safety": {"status": safety_status, "notes": notes},
    }


def _ensure_demo_pack_advisor_suggestions(workspace_root: Path) -> dict[str, object]:
    targets = _load_expected_pack_advisor_paths(workspace_root)
    payload = _build_pack_advisor_suggestions(workspace_root)
    kept = 0
    written = 0
    for path in targets:
        if path.exists():
            obj, valid = _load_json(path)
            if valid and isinstance(obj, dict) and _pack_advisor_semantic_ok(obj):
                kept += 1
                continue
        _write_json_atomic(path, payload)
        written += 1
    action = "written" if written else "kept"
    return {
        "status": "OK",
        "action": action,
        "path": str(targets[0]),
        "paths": [str(p) for p in targets],
        "kept": kept,
        "written": written,
    }


def _collect_pack_manifests(core_root: Path, workspace_root: Path) -> list[tuple[Path, str]]:
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
    obj, valid = _load_json(ref_path)
    if not valid or not isinstance(obj, dict):
        return None
    meta = obj.get("meta") if isinstance(obj, dict) else None
    if isinstance(meta, dict) and isinstance(meta.get("id"), str):
        return meta.get("id")
    return None


def _extract_format_id(ref_path: Path) -> str | None:
    obj, valid = _load_json(ref_path)
    if not valid or not isinstance(obj, dict):
        return None
    fmt_id = obj.get("id")
    return fmt_id if isinstance(fmt_id, str) else None


def _pack_index_has_expected(obj: dict) -> bool:
    packs = obj.get("packs") if isinstance(obj, dict) else None
    if not isinstance(packs, list):
        return False
    pack_ids = {
        p.get("pack_id")
        for p in packs
        if isinstance(p, dict) and isinstance(p.get("pack_id"), str)
    }
    expected = {"pack-software-architecture", "pack-document-management"}
    if not expected.issubset(pack_ids):
        return False
    if not isinstance(obj.get("hard_conflicts"), list):
        return False
    if not isinstance(obj.get("soft_conflicts"), list):
        return False
    return True


def _build_pack_index(workspace_root: Path, core_root: Path) -> tuple[dict, dict]:
    pack_records: dict[str, dict] = {}
    pack_manifest_sha256_map: dict[str, str] = {}
    hard_conflicts: list[dict] = []
    soft_conflicts: list[dict] = []
    source_priority = {"core": 0, "workspace": 1}

    for path, source in _collect_pack_manifests(core_root, workspace_root):
        try:
            data = path.read_bytes()
        except Exception:
            continue
        manifest, valid = _load_json(path)
        if not valid or not isinstance(manifest, dict):
            continue
        pack_id = manifest.get("pack_id")
        if not isinstance(pack_id, str):
            continue
        pack_manifest_sha256_map[pack_id] = _sha256_bytes(data)

        if pack_id in pack_records:
            prev = pack_records[pack_id]
            if source_priority[source] < source_priority.get(prev.get("source", "core"), 0):
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
                continue
            cap_id = _extract_capability_id(ref_path)
            if cap_id:
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
                continue
            fmt_id = _extract_format_id(ref_path)
            if fmt_id:
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

    for pack_id in ("pack-document-management", "pack-software-architecture"):
        if pack_id in pack_records:
            continue
        pack_records[pack_id] = {
            "pack_id": pack_id,
            "version": "v1",
            "lifecycle_state": "experimental",
            "namespace_prefix": "",
            "intents": [],
            "workflows": [],
            "formats": [],
            "capability_ids": [],
            "format_ids": [],
            "iso_kernel_refs": {},
            "source": "core",
            "path": str(Path("packs") / pack_id / "pack.manifest.v1.json"),
        }

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
        "\n".join(
            f"{pid}:{pack_manifest_sha256_map.get(pid, '')}" for pid in sorted(pack_records)
        ).encode("utf-8")
    )

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

    cursor_obj = {
        "version": "v1",
        "last_pack_list_sha256": pack_list_sha,
        "pack_manifest_sha256_map": pack_manifest_sha256_map,
        "last_index_sha256": index_sha,
    }

    return index_obj, cursor_obj


def _ensure_demo_pack_capability_index(workspace_root: Path) -> dict[str, str]:
    index_path = _pack_index_path(workspace_root)
    if index_path.exists():
        obj, valid = _load_json(index_path)
        if valid and isinstance(obj, dict) and _pack_index_has_expected(obj):
            return {"status": "OK", "action": "kept", "path": str(index_path)}

    core_root = _repo_root()
    try:
        index_obj, cursor_obj = _build_pack_index(workspace_root, core_root)
        _write_json_atomic(index_path, index_obj)
        _write_json_atomic(_pack_index_cursor_path(workspace_root), cursor_obj)
        return {"status": "OK", "action": "written", "path": str(index_path)}
    except Exception:
        fallback = {
            "version": "v1",
            "workspace_root": str(workspace_root),
            "packs": [
                {"pack_id": "pack-document-management"},
                {"pack_id": "pack-software-architecture"},
            ],
            "hard_conflicts": [],
            "soft_conflicts": [],
            "hashes": {"index_sha256": "", "pack_list_sha256": ""},
        }
        _write_json_atomic(index_path, fallback)
        return {"status": "FALLBACK", "action": "written", "path": str(index_path)}


def _ensure_demo_pack_selection_trace(workspace_root: Path) -> dict[str, object]:
    targets = _load_expected_pack_selection_paths(workspace_root)
    payload = _build_pack_selection_trace(workspace_root)
    kept = 0
    written = 0
    for path in targets:
        if path.exists():
            obj, valid = _load_json(path)
            if valid and isinstance(obj, dict) and _selection_trace_has_expected(obj):
                kept += 1
                continue
        _write_json_atomic(path, payload)
        written += 1
    action = "written" if written else "kept"
    return {
        "status": "OK",
        "action": action,
        "path": str(targets[0]),
        "paths": [str(p) for p in targets],
        "kept": kept,
        "written": written,
    }


def _public_candidates_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "learning" / "public_candidates.v1.json"


def _public_candidates_pointer_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "artifacts" / "public_candidates.pointer.v1.json"


def _public_candidates_ok(obj: dict) -> bool:
    candidates = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(candidates, list):
        return False
    kinds = {c.get("kind") for c in candidates if isinstance(c, dict)}
    if not {"PACK_HINT", "FORMAT_HINT"}.issubset(kinds):
        return False
    sanitization = obj.get("sanitization") if isinstance(obj, dict) else None
    status = sanitization.get("status") if isinstance(sanitization, dict) else None
    return status in {"OK", "WARN"}


def _demo_public_candidates_payload(workspace_root: Path) -> dict:
    candidates = [
        {
            "kind": "FORMAT_HINT",
            "key": "format_hint_seed",
            "value": {"note": "seed"},
            "confidence": 0.1,
            "evidence_refs": ["seed"],
        },
        {
            "kind": "PACK_HINT",
            "key": "pack_hint_seed",
            "value": {"note": "seed"},
            "confidence": 0.1,
            "evidence_refs": ["seed"],
        },
    ]
    candidates.sort(key=lambda c: (str(c.get("kind") or ""), str(c.get("key") or "")))
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root.resolve()),
        "source_counts": {"evidence_runs": 0, "dlq_items": 0},
        "candidates": candidates,
        "sanitization": {"status": "OK", "removed_tokens_count": 0, "notes": []},
    }


def _ensure_demo_public_candidates_bundle(workspace_root: Path) -> dict[str, str]:
    bundle_path = _public_candidates_path(workspace_root)
    if bundle_path.exists():
        obj, valid = _load_json(bundle_path)
        if valid and isinstance(obj, dict) and _public_candidates_ok(obj):
            return {"status": "OK", "action": "kept", "path": str(bundle_path)}
    _write_json_atomic(bundle_path, _demo_public_candidates_payload(workspace_root))
    return {"status": "OK", "action": "written", "path": str(bundle_path)}


def _pointer_matches_source(pointer: dict, source_sha: str, workspace_root: Path) -> bool:
    if pointer.get("sha256") != source_sha:
        return False
    stored_rel = pointer.get("stored_path")
    if not isinstance(stored_rel, str) or not stored_rel.strip():
        return False
    stored_path = (workspace_root / Path(stored_rel).as_posix()).resolve()
    try:
        stored_path.relative_to(workspace_root.resolve())
    except Exception:
        return False
    return stored_path.exists()


def _ensure_demo_public_candidates_pointer(workspace_root: Path) -> dict[str, str]:
    source_rel = Path(".cache") / "learning" / "public_candidates.v1.json"
    source_path = (workspace_root / source_rel).resolve()
    pointer_path = _public_candidates_pointer_path(workspace_root)
    if not source_path.exists():
        return {"status": "FAIL", "action": "missing_source", "pointer_path": str(pointer_path)}
    source_sha = _file_sha256(source_path)
    if not source_sha:
        return {"status": "FAIL", "action": "hash_failed", "pointer_path": str(pointer_path)}
    if pointer_path.exists():
        obj, valid = _load_json(pointer_path)
        if valid and isinstance(obj, dict) and _pointer_matches_source(obj, source_sha, workspace_root):
            return {"status": "OK", "action": "kept", "pointer_path": str(pointer_path)}
    try:
        from src.artifacts import store

        pointer = store.put(workspace_root=workspace_root, relpath=source_rel.as_posix())
        store.write_pointer(pointer_path, pointer)
        return {"status": "OK", "action": "written", "pointer_path": str(pointer_path)}
    except Exception:
        return {"status": "FAIL", "action": "write_failed", "pointer_path": str(pointer_path)}
