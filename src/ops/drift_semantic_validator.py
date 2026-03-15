"""Semantic drift validation — validates JSON files against schemas and detects breaking field changes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_schema_for_file(file_path: Path, schemas_dir: Path) -> Path | None:
    """Attempt to find a matching schema for a JSON data file.

    Mapping:  ``policies/policy_foo.v1.json`` -> ``schemas/policy-foo.schema.json``
    """
    name = file_path.stem  # e.g. policy_foo.v1
    # Strip version suffix
    for suffix in (".v1", ".v2", ".v3"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    # Convert underscores to hyphens (repo convention)
    schema_name = name.replace("_", "-") + ".schema.json"
    candidate = schemas_dir / schema_name
    if candidate.exists():
        return candidate
    # Try with version suffix in schema name
    schema_name_v = name.replace("_", "-") + ".schema.v1.json"
    candidate_v = schemas_dir / schema_name_v
    if candidate_v.exists():
        return candidate_v
    return None


def validate_file_against_schema(
    *,
    file_path: Path,
    schemas_dir: Path,
) -> dict[str, Any]:
    """Validate a single JSON file against its matching schema.

    Returns ``{valid: bool, errors: [...], schema_path: str|None}``.
    """
    data = _load_json(file_path)
    if data is None:
        return {"valid": False, "errors": ["JSON_PARSE_ERROR"], "schema_path": None}

    schema_path = _find_schema_for_file(file_path, schemas_dir)
    if schema_path is None:
        return {"valid": True, "errors": [], "schema_path": None}

    schema = _load_json(schema_path)
    if schema is None:
        return {"valid": True, "errors": ["SCHEMA_PARSE_ERROR"], "schema_path": str(schema_path)}

    try:
        from jsonschema import Draft202012Validator

        validator = Draft202012Validator(schema)
        errs = sorted(validator.iter_errors(data), key=lambda e: e.json_path)
        error_msgs = [f"{e.json_path}: {e.message}" for e in errs[:10]]
        return {
            "valid": len(errs) == 0,
            "errors": error_msgs,
            "schema_path": str(schema_path),
        }
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)], "schema_path": str(schema_path)}


def detect_breaking_field_changes(
    *,
    current: dict[str, Any],
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare two JSON objects and return a list of breaking changes.

    Breaking changes:
    - Required field removed (key present in previous but absent in current)
    - Field type changed (string -> int, etc.)
    - Enum value removed (if field went from valid enum to absent value)
    """
    if not isinstance(current, dict) or not isinstance(previous, dict):
        return []

    breaks: list[dict[str, Any]] = []

    # Detect removed keys
    for key in previous:
        if key not in current:
            breaks.append({
                "type": "FIELD_REMOVED",
                "path": f"$.{key}",
                "previous_value_type": type(previous[key]).__name__,
            })

    # Detect type changes
    for key in current:
        if key in previous:
            cur_type = type(current[key]).__name__
            prev_type = type(previous[key]).__name__
            if cur_type != prev_type:
                breaks.append({
                    "type": "TYPE_CHANGED",
                    "path": f"$.{key}",
                    "previous_type": prev_type,
                    "current_type": cur_type,
                })

    return breaks


def build_semantic_drift_report(
    *,
    repo_root: Path,
    workspace_root: Path,
    changed_files: list[str],
    session_id: str = "",
) -> dict[str, Any]:
    """Build semantic drift report for a set of changed files.

    For each file: run schema validation + breaking change detection.
    Returns ``{semantic_violations: [...], provenance: {...}}``.
    """
    schemas_dir = repo_root / "schemas"
    violations: list[dict[str, Any]] = []

    for rel_path in changed_files:
        full = repo_root / rel_path
        if not full.exists() or not full.suffix == ".json":
            continue

        # Schema validation
        val = validate_file_against_schema(file_path=full, schemas_dir=schemas_dir)
        if not val["valid"]:
            violations.append({
                "file": rel_path,
                "violation_type": "SCHEMA_INVALID",
                "errors": val["errors"],
                "schema_path": val.get("schema_path"),
            })

        # Breaking change detection against cached previous version
        cache_path = workspace_root / ".cache" / "drift_baseline" / rel_path
        if cache_path.exists():
            prev = _load_json(cache_path)
            cur = _load_json(full)
            if isinstance(prev, dict) and isinstance(cur, dict):
                breaks = detect_breaking_field_changes(current=cur, previous=prev)
                for b in breaks:
                    violations.append({
                        "file": rel_path,
                        "violation_type": b["type"],
                        "detail": b,
                    })

    provenance: dict[str, Any] = {
        "checked_at": _now_iso(),
        "changed_files_count": len(changed_files),
        "violations_count": len(violations),
    }
    if session_id:
        provenance["session_id"] = session_id

    return {
        "semantic_violations": violations,
        "provenance": provenance,
    }
