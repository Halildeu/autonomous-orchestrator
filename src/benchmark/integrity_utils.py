from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTEGRITY_INPUTS = {
    "system_status": Path(".cache") / "reports" / "system_status.v1.json",
    "pack_index": Path(".cache") / "index" / "pack_capability_index.v1.json",
    "quality_gate": Path(".cache") / "index" / "quality_gate_report.v1.json",
    "repo_hygiene": Path(".cache") / "repo_hygiene" / "report.json",
    "harvest": Path(".cache") / "learning" / "public_candidates.v1.json",
    "script_budget": Path(".cache") / "script_budget" / "report.json",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _relpath_or_fallback(workspace_root: Path, target: Path, fallback: str) -> str:
    try:
        return target.relative_to(workspace_root).as_posix()
    except Exception:
        return fallback


def load_policy_integrity(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_integrity.v1.json"
    core_policy = core_root / "policies" / "policy_integrity.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {
            "version": "v1",
            "enabled": True,
            "verify_on_read_required": True,
            "allow_report_only_when_missing_sources": True,
            "inputs": {
                "system_status": {"required": True, "on_mismatch": "FAIL"},
                "pack_index": {"required": True, "on_mismatch": "FAIL"},
                "quality_gate": {"required": False, "on_mismatch": "WARN"},
                "repo_hygiene": {"required": False, "on_mismatch": "WARN"},
                "harvest": {"required": False, "on_mismatch": "WARN"},
                "script_budget": {"required": True, "on_mismatch": "FAIL"},
            },
        }
    obj = _load_json(path)
    return obj if isinstance(obj, dict) else {}


def collect_input_paths(*, workspace_root: Path) -> dict[str, Path]:
    return {k: (workspace_root / v).resolve() for k, v in INTEGRITY_INPUTS.items()}


def compute_input_hashes(*, input_paths: dict[str, Path]) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for key, path in input_paths.items():
        if not path.exists() or not path.is_file():
            hashes[key] = None
            continue
        hashes[key] = _hash_bytes(path.read_bytes())
    return hashes


def load_previous_snapshot(*, workspace_root: Path) -> dict[str, Any] | None:
    path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def resolve_integrity_snapshot_ref(*, workspace_root: Path) -> Path | None:
    raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    if not raw_path.exists():
        return None
    try:
        obj = _load_json(raw_path)
    except Exception:
        return None
    ref = obj.get("integrity_snapshot_ref") if isinstance(obj, dict) else None
    if not isinstance(ref, str) or not ref.strip():
        return None
    ref_path = (workspace_root / ref).resolve()
    try:
        _ensure_inside_workspace(workspace_root, ref_path)
    except Exception:
        return None
    return ref_path


def build_integrity_snapshot(
    *,
    workspace_root: Path,
    core_root: Path,
    policy: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    input_paths = collect_input_paths(workspace_root=workspace_root)
    input_hashes = compute_input_hashes(input_paths=input_paths)

    prev_hashes = previous_snapshot.get("input_hashes") if isinstance(previous_snapshot, dict) else None
    prev_hashes = prev_hashes if isinstance(prev_hashes, dict) else {}

    inputs_policy = policy.get("inputs") if isinstance(policy, dict) else {}
    inputs_policy = inputs_policy if isinstance(inputs_policy, dict) else {}

    mismatch_keys: set[str] = set()
    missing_required: set[str] = set()

    for key, path in input_paths.items():
        curr = input_hashes.get(key)
        prev = prev_hashes.get(key)
        rule = inputs_policy.get(key) if isinstance(inputs_policy.get(key), dict) else {}
        required = bool(rule.get("required", False))
        if curr is None and required:
            missing_required.add(key)
        if previous_snapshot is not None and prev != curr:
            mismatch_keys.add(key)

    if previous_snapshot is None and missing_required:
        mismatch_keys.update(missing_required)

    mismatch_paths: list[str] = []
    for key in sorted(mismatch_keys):
        rel = str(INTEGRITY_INPUTS.get(key, key))
        mismatch_paths.append(_relpath_or_fallback(workspace_root, input_paths[key], rel))

    verify_on_read_result = "PASS"
    allow_report_only = bool(policy.get("allow_report_only_when_missing_sources", True))
    if previous_snapshot is None and missing_required:
        verify_on_read_result = "WARN" if allow_report_only else "FAIL"
    elif mismatch_keys:
        severity = "WARN"
        for key in mismatch_keys:
            rule = inputs_policy.get(key) if isinstance(inputs_policy.get(key), dict) else {}
            if str(rule.get("on_mismatch", "WARN")) == "FAIL":
                severity = "FAIL"
                break
        verify_on_read_result = severity

    pointer_store_head = None
    pointer_path = workspace_root / ".cache" / "index" / "pointer_store_head.v1.json"
    if pointer_path.exists():
        try:
            obj = _load_json(pointer_path)
            head = obj.get("head") if isinstance(obj, dict) else None
            pointer_store_head = str(head) if head is not None else None
        except Exception:
            pointer_store_head = None

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "input_hashes": input_hashes,
        "pointer_store_head": pointer_store_head,
        "verify_on_read_result": verify_on_read_result,
        "mismatch_count": len(mismatch_paths),
        "mismatches": mismatch_paths,
    }
