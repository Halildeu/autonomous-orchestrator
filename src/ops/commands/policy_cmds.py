from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.ops.commands.common import repo_root, run_step, warn, write_json
from src.ops.reaper import parse_bool as parse_reaper_bool


def schema_path_for_policy_name(root: Path, policy_filename: str) -> Path:
    name = Path(policy_filename).name
    base = name.split(".v", 1)[0] if ".v" in name else name.rsplit(".json", 1)[0]
    schema_name = base.replace("_", "-") + ".schema.json"
    return root / "schemas" / schema_name


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def policy_paths_from_obj(obj: Any, prefix: str = "") -> dict[str, Any]:
    # Flatten leaf values to dot paths (dict recursion only; lists treated as leaves).
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            if not isinstance(k, str):
                continue
            path = f"{prefix}.{k}" if prefix else k
            v = obj.get(k)
            if isinstance(v, dict):
                out.update(policy_paths_from_obj(v, prefix=path))
            else:
                out[path] = v
    else:
        out[prefix or "$"] = obj
    return out


def cmd_policy_export(args: argparse.Namespace) -> int:
    root = repo_root()
    name = Path(str(args.name)).name
    policy_path = root / "policies" / name
    if not policy_path.exists():
        warn(f"ERROR: policy not found: {name}")
        return 2

    content = policy_path.read_text(encoding="utf-8")
    if args.out:
        out_path = Path(str(args.out))
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    print(content.rstrip("\n"))
    return 0


def cmd_policy_validate(args: argparse.Namespace) -> int:
    root = repo_root()
    file_path = Path(str(args.file))
    file_path = (root / file_path).resolve() if not file_path.is_absolute() else file_path.resolve()
    if not file_path.exists():
        warn(f"FAIL file={file_path} error=FILE_NOT_FOUND")
        return 2

    try:
        infer_schema = parse_reaper_bool(str(args.infer_schema))
    except ValueError:
        warn(f"FAIL file={file_path} error=INVALID_ARGS")
        return 2

    try:
        instance = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        warn(f"FAIL file={file_path} error=JSON_INVALID")
        return 2

    # Strict mapping by policy filename (default): policy_security.v1.json -> schemas/policy-security.schema.json.
    mapped_schema = schema_path_for_policy_name(root, file_path.name)
    schema_to_use: Path | None = mapped_schema if mapped_schema.exists() else None
    inferred = False

    if schema_to_use is None:
        if not infer_schema:
            warn(f"FAIL file={file_path} schema={mapped_schema.name} error=SCHEMA_NOT_FOUND")
            return 2

        # Best-effort inference (opt-in): try to infer by validating against all known policy schemas.
        schema_candidates = sorted((root / "schemas").glob("policy-*.schema.json"), key=lambda p: p.name)
        best_schema: Path | None = None
        best_errors: list[str] = []
        best_count: int | None = None
        matches: list[Path] = []

        for schema_path in schema_candidates:
            try:
                validator = load_validator(schema_path)
                errors = [e.message for e in validator.iter_errors(instance)]
                if not errors:
                    matches.append(schema_path)
                    best_schema = schema_path
                    best_errors = []
                    best_count = 0
                    break
                if best_count is None or len(errors) < best_count:
                    best_schema = schema_path
                    best_errors = errors[:5]
                    best_count = len(errors)
            except Exception:
                continue

        if matches:
            schema_to_use = matches[0]
            inferred = True
        elif best_schema is not None:
            schema_to_use = best_schema
            inferred = True
            warn(f"SCHEMA_INFERRED schema={schema_to_use.name}")
            warn(f"WARN file={file_path} error=SCHEMA_INFERRED errors={best_errors}")
        else:
            warn(f"FAIL file={file_path} error=SCHEMA_NOT_FOUND")
            return 2

    try:
        validator = load_validator(schema_to_use)
        errors = [e.message for e in validator.iter_errors(instance)]
        if errors:
            warn(f"FAIL file={file_path} schema={schema_to_use.name} error=SCHEMA_INVALID")
            for e in errors[:5]:
                warn(f"  - {e}")
            return 2
    except Exception:
        warn(f"FAIL file={file_path} schema={schema_to_use.name} error=SCHEMA_INVALID")
        return 2

    if inferred:
        print(f"SCHEMA_INFERRED schema={schema_to_use.name}")
    print(f"OK file={file_path} schema={schema_to_use.name}")
    return 0


def cmd_policy_diff(args: argparse.Namespace) -> int:
    root = repo_root()
    a_path = Path(str(args.a))
    b_path = Path(str(args.b))
    a_path = (root / a_path).resolve() if not a_path.is_absolute() else a_path.resolve()
    b_path = (root / b_path).resolve() if not b_path.is_absolute() else b_path.resolve()

    if not a_path.exists():
        warn(f"FAIL a={a_path} error=FILE_NOT_FOUND")
        return 2
    if not b_path.exists():
        warn(f"FAIL b={b_path} error=FILE_NOT_FOUND")
        return 2

    try:
        a_obj = json.loads(a_path.read_text(encoding="utf-8"))
        b_obj = json.loads(b_path.read_text(encoding="utf-8"))
    except Exception:
        warn("FAIL error=JSON_INVALID")
        return 2

    a_paths = policy_paths_from_obj(a_obj)
    b_paths = policy_paths_from_obj(b_obj)

    changed = sorted([k for k in a_paths.keys() if k in b_paths and a_paths[k] != b_paths[k]])
    added = sorted([k for k in b_paths.keys() if k not in a_paths])
    removed = sorted([k for k in a_paths.keys() if k not in b_paths])

    out = {"changed_keys": changed, "added_keys": added, "removed_keys": removed}
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def cmd_policy_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    file_path = Path(str(args.file))
    file_path = (root / file_path).resolve() if not file_path.is_absolute() else file_path.resolve()
    if not file_path.exists():
        warn(f"FAIL file={file_path} error=FILE_NOT_FOUND")
        return 2

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn(f"FAIL file={file_path} error=INVALID_ARGS")
        return 2

    try:
        infer_schema = parse_reaper_bool(str(args.infer_schema))
    except ValueError:
        warn(f"FAIL file={file_path} error=INVALID_ARGS")
        return 2

    validate_args = argparse.Namespace(file=str(file_path), infer_schema=str(args.infer_schema))
    validate_rc = cmd_policy_validate(validate_args)
    if validate_rc != 0:
        warn(f"FAIL file={file_path} error=SCHEMA_INVALID")
        return 2

    if dry_run:
        rc, _, _ = run_step(
            root,
            [
                "python",
                "-m",
                "src.ops.manage",
                "policy-check",
                "--source",
                "fixtures",
            ],
            stage="policy-check",
        )
        if rc != 0:
            return 2
        print("OK dry_run=true")
        return 0

    # Ensure we only apply into policies/<basename>.
    target = root / "policies" / file_path.name
    if target.resolve() != target:
        warn(f"FAIL file={file_path} error=INVALID_TARGET")
        return 2

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

    rc, _, _ = run_step(
        root,
        [
            "python",
            "-m",
            "src.ops.manage",
            "policy-check",
            "--source",
            "fixtures",
        ],
        stage="policy-check",
    )
    if rc != 0:
        return 2

    rc, _, _ = run_step(
        root,
        ["python", "supply_chain/sbom.py"],
        stage="sbom",
    )
    if rc != 0:
        return 2
    rc, _, _ = run_step(
        root,
        ["python", "supply_chain/sign.py"],
        stage="sign",
    )
    if rc != 0:
        return 2
    rc, _, _ = run_step(
        root,
        ["python", "supply_chain/verify.py"],
        stage="verify",
    )
    if rc != 0:
        return 2

    print("OK dry_run=false")
    return 0


def register_policy_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_policy = parent.add_parser("policy", help="Safe policy editing helpers (export/validate/diff/apply).")
    policy_sub = ap_policy.add_subparsers(dest="policy_command", required=True)

    ap_p_exp = policy_sub.add_parser("export", help="Export a policy by name (policies/<name>).")
    ap_p_exp.add_argument("--name", required=True, help="Policy filename, e.g. policy_security.v1.json")
    ap_p_exp.add_argument("--out", help="Optional output path.")
    ap_p_exp.set_defaults(func=cmd_policy_export)

    ap_p_val = policy_sub.add_parser("validate", help="Validate one policy file against its schema.")
    ap_p_val.add_argument("--file", required=True, help="Path to a policy JSON file.")
    ap_p_val.add_argument("--infer-schema", default="false", help="true|false (default: false).")
    ap_p_val.set_defaults(func=cmd_policy_validate)

    ap_p_diff = policy_sub.add_parser("diff", help="Show a compact JSON diff of two policy files.")
    ap_p_diff.add_argument("--a", required=True, help="Path to file A.")
    ap_p_diff.add_argument("--b", required=True, help="Path to file B.")
    ap_p_diff.set_defaults(func=cmd_policy_diff)

    ap_p_apply = policy_sub.add_parser("apply", help="Apply a validated policy file into policies/ (safe).")
    ap_p_apply.add_argument("--file", required=True, help="Path to the new policy file (same basename).")
    ap_p_apply.add_argument("--dry-run", default="true", help="true|false")
    ap_p_apply.add_argument("--infer-schema", default="false", help="true|false (default: false).")
    ap_p_apply.set_defaults(func=cmd_policy_apply)
