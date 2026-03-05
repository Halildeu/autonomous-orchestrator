#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = "policies/policy_ux_catalog_enforcement.v1.json"
DEFAULT_OUT_PATH = ".cache/reports/ux_catalog_enforcement.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid_json_root:{path}")
    return obj


def _match_any(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def _normalize_rel(path: str) -> str:
    norm = str(path or "").strip().replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _git_changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "diff",
        "--name-only",
        "--diff-filter=ACMRTUXB",
        base,
        head,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git_diff_failed").strip())
    files = [_normalize_rel(ln) for ln in (proc.stdout or "").splitlines() if _normalize_rel(ln)]
    return sorted(set(files))


def _default_diff_refs(repo_root: Path) -> tuple[str, str]:
    event = str((Path.cwd().joinpath(".github").exists() and "") or "")
    _ = event
    # CI tarafinda pull_request merge commit oldugunda HEAD^1/HEAD^2 kullan.
    # Diger durumlarda HEAD~1..HEAD fallback.
    try:
        left = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^1"],
            text=True,
            capture_output=True,
            check=False,
        )
        right = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^2"],
            text=True,
            capture_output=True,
            check=False,
        )
        if left.returncode == 0 and right.returncode == 0:
            base_parent = left.stdout.strip()
            pr_head_parent = right.stdout.strip()
            mb = subprocess.run(
                ["git", "-C", str(repo_root), "merge-base", base_parent, pr_head_parent],
                text=True,
                capture_output=True,
                check=False,
            )
            if mb.returncode == 0 and mb.stdout.strip():
                return mb.stdout.strip(), pr_head_parent
    except Exception:
        pass

    return "HEAD~1", "HEAD"


def _build_lock_index(lock_obj: dict[str, Any]) -> tuple[set[str], dict[str, set[str]]]:
    themes = lock_obj.get("themes") if isinstance(lock_obj.get("themes"), list) else []
    theme_ids: set[str] = set()
    sub_by_theme: dict[str, set[str]] = {}
    for item in themes:
        if not isinstance(item, dict):
            continue
        theme_id = str(item.get("theme_id") or "").strip()
        if not theme_id:
            continue
        theme_ids.add(theme_id)
        subs = item.get("subthemes") if isinstance(item.get("subthemes"), list) else []
        sub_ids: set[str] = set()
        for sub in subs:
            if not isinstance(sub, str):
                continue
            sid = str(sub).strip()
            if sid:
                sub_ids.add(sid)
        sub_by_theme[theme_id] = sub_ids
    return theme_ids, sub_by_theme


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--policy-path", default=DEFAULT_POLICY_PATH)
    ap.add_argument("--base", default="")
    ap.add_argument("--head", default="")
    ap.add_argument("--changed-files", default="", help="Comma separated file list (optional).")
    ap.add_argument("--out", default=DEFAULT_OUT_PATH)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    policy_path = (repo_root / str(args.policy_path)).resolve()
    out_path = Path(str(args.out))
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()

    errors: list[str] = []
    warnings: list[str] = []

    if not policy_path.exists():
        errors.append(f"policy_missing:{policy_path.as_posix()}")
        report = {
            "version": "v1",
            "kind": "ux-catalog-enforcement-report",
            "generated_at": _now_iso(),
            "status": "FAIL",
            "repo_root": str(repo_root),
            "policy_path": str(policy_path),
            "errors": errors,
            "warnings": warnings,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL", "error_code": "POLICY_MISSING", "out": str(out_path)}, ensure_ascii=False))
        return 2

    policy = _load_json(policy_path)
    enforcement_mode = str(policy.get("enforcement_mode") or "blocking").strip().lower()
    lock_file_rel = str(policy.get("lock_file") or "").strip()
    lock_path = (repo_root / lock_file_rel).resolve() if lock_file_rel else Path("")
    if not lock_file_rel:
        errors.append("policy_lock_file_missing")
    elif not lock_path.exists():
        errors.append(f"lock_missing:{lock_file_rel}")

    lock_obj: dict[str, Any] = {}
    theme_ids: set[str] = set()
    sub_by_theme: dict[str, set[str]] = {}
    if not errors:
        lock_obj = _load_json(lock_path)
        theme_ids, sub_by_theme = _build_lock_index(lock_obj)
        if not theme_ids:
            errors.append("lock_theme_index_empty")

    include_globs = []
    exclude_globs = []
    scope = policy.get("enforce_scope") if isinstance(policy.get("enforce_scope"), dict) else {}
    if isinstance(scope.get("include_globs"), list):
        include_globs = [str(x).strip() for x in scope["include_globs"] if isinstance(x, str) and str(x).strip()]
    if isinstance(scope.get("exclude_globs"), list):
        exclude_globs = [str(x).strip() for x in scope["exclude_globs"] if isinstance(x, str) and str(x).strip()]

    changed_files: list[str] = []
    diff_base = str(args.base or "").strip()
    diff_head = str(args.head or "").strip()
    try:
        raw_changed = str(args.changed_files or "").strip()
        if raw_changed:
            changed_files = sorted(set(_normalize_rel(item) for item in raw_changed.split(",") if _normalize_rel(item)))
        else:
            if not diff_base or not diff_head:
                diff_base, diff_head = _default_diff_refs(repo_root)
            changed_files = _git_changed_files(repo_root, diff_base, diff_head)
    except Exception as exc:
        errors.append(f"diff_collect_failed:{exc}")

    scoped_files: list[str] = []
    for rel in changed_files:
        in_scope = _match_any(rel, include_globs) if include_globs else True
        excluded = _match_any(rel, exclude_globs) if exclude_globs else False
        if in_scope and not excluded:
            scoped_files.append(rel)

    change_map_cfg = policy.get("change_map") if isinstance(policy.get("change_map"), dict) else {}
    change_map_required = bool(change_map_cfg.get("required", True))
    change_map_path_rel = str(change_map_cfg.get("path") or "").strip()
    min_entries = int(change_map_cfg.get("min_entries") or 0)
    change_map_path = (repo_root / change_map_path_rel).resolve() if change_map_path_rel else Path("")

    map_entries: list[dict[str, Any]] = []
    map_errors: list[str] = []
    map_warnings: list[str] = []
    map_index: dict[str, dict[str, Any]] = {}

    if scoped_files:
        if change_map_required and (not change_map_path_rel or not change_map_path.exists()):
            map_errors.append(f"change_map_missing:{change_map_path_rel or 'unset'}")
        if change_map_path_rel and change_map_path.exists():
            try:
                map_obj = _load_json(change_map_path)
                entries = map_obj.get("entries") if isinstance(map_obj.get("entries"), list) else []
                for idx, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        map_errors.append(f"entry_not_object:{idx}")
                        continue
                    rel = _normalize_rel(str(entry.get("path") or ""))
                    theme_id = str(entry.get("ux_theme_id") or "").strip()
                    sub_id = str(entry.get("ux_subtheme_id") or "").strip()
                    if not rel or not theme_id or not sub_id:
                        map_errors.append(f"entry_required_fields_missing:{idx}")
                        continue
                    if rel in map_index:
                        map_errors.append(f"entry_duplicate_path:{rel}")
                        continue
                    if theme_id not in theme_ids:
                        map_errors.append(f"entry_invalid_theme_id:{rel}:{theme_id}")
                    elif sub_id not in sub_by_theme.get(theme_id, set()):
                        map_errors.append(f"entry_invalid_subtheme_id:{rel}:{theme_id}:{sub_id}")
                    map_index[rel] = {"ux_theme_id": theme_id, "ux_subtheme_id": sub_id}
                    map_entries.append({
                        "path": rel,
                        "ux_theme_id": theme_id,
                        "ux_subtheme_id": sub_id,
                    })
            except Exception as exc:
                map_errors.append(f"change_map_invalid_json:{exc}")

        if len(map_entries) < min_entries:
            map_errors.append(f"change_map_min_entries_violation:{len(map_entries)}<{min_entries}")

    missing_mappings: list[str] = []
    if scoped_files:
        for rel in scoped_files:
            if rel not in map_index:
                missing_mappings.append(rel)

    extra_entries = sorted(rel for rel in map_index.keys() if rel not in set(scoped_files))
    if extra_entries:
        map_warnings.append("change_map_contains_non_scoped_entries")

    if missing_mappings:
        map_errors.extend([f"missing_mapping:{rel}" for rel in missing_mappings])

    errors.extend(map_errors)
    warnings.extend(map_warnings)

    status = "OK"
    if errors:
        status = "FAIL" if enforcement_mode == "blocking" else "WARN"
    elif scoped_files and not map_entries:
        status = "FAIL" if enforcement_mode == "blocking" else "WARN"

    report = {
        "version": "v1",
        "kind": "ux-catalog-enforcement-report",
        "generated_at": _now_iso(),
        "status": status,
        "enforcement_mode": enforcement_mode,
        "repo_root": str(repo_root),
        "policy_path": str(policy_path),
        "lock_path": lock_file_rel,
        "change_map_path": change_map_path_rel,
        "diff": {
            "base": diff_base,
            "head": diff_head,
            "changed_files_count": len(changed_files),
            "scoped_changed_files_count": len(scoped_files),
            "scoped_changed_files": scoped_files,
        },
        "lock": {
            "theme_count": len(theme_ids),
            "subtheme_count": sum(len(v) for v in sub_by_theme.values()),
            "lock_hash_sha256": str(lock_obj.get("lock_hash_sha256") or ""),
        },
        "change_map": {
            "entries_count": len(map_entries),
            "covered_count": max(0, len(scoped_files) - len(missing_mappings)),
            "missing_mappings": missing_mappings,
            "extra_entries": extra_entries,
            "entries": map_entries,
        },
        "errors": errors,
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": status,
        "enforcement_mode": enforcement_mode,
        "scoped_changed_files_count": len(scoped_files),
        "entries_count": len(map_entries),
        "missing_mappings": len(missing_mappings),
        "errors": len(errors),
        "warnings": len(warnings),
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    if status == "FAIL" and enforcement_mode == "blocking":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
