#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_relpath(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid relative path")
    p = Path(value.strip())
    if p.is_absolute():
        raise ValueError(f"absolute path not allowed: {value}")
    if ".." in p.parts:
        raise ValueError(f"path traversal not allowed: {value}")
    norm = p.as_posix()
    if not norm or norm == ".":
        raise ValueError("empty relative path")
    return norm


def _collect_standard_paths(lock_obj: dict[str, Any]) -> list[str]:
    required_files = lock_obj.get("required_files")
    if not isinstance(required_files, list):
        raise ValueError("standards.lock required_files must be a list")

    standard_sources = lock_obj.get("standard_sources")
    if not isinstance(standard_sources, dict):
        raise ValueError("standards.lock standard_sources must be an object")

    out: list[str] = []
    seen: set[str] = set()

    def add_path(raw: Any) -> None:
        rel = _safe_relpath(raw)
        if rel in seen:
            return
        seen.add(rel)
        out.append(rel)

    for rel in required_files:
        add_path(rel)
    for rel in standard_sources.values():
        add_path(rel)

    return out


def _load_manifest_targets(manifest_path: Path) -> list[Path]:
    manifest = _load_json(manifest_path)
    repos = manifest.get("repos")
    if not isinstance(repos, list):
        return []
    targets: list[Path] = []
    for item in repos:
        if not isinstance(item, dict):
            continue
        repo_root = item.get("repo_root")
        if not isinstance(repo_root, str) or not repo_root.strip():
            continue
        targets.append(Path(repo_root.strip()).expanduser().resolve())
    return targets


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p.resolve())
    return out


def _run_standards_validation(source_root: Path, target_root: Path) -> dict[str, Any]:
    check_script = (source_root / "ci" / "check_standards_lock.py").resolve()
    if not check_script.exists():
        return {"status": "FAIL", "reason": "CHECK_SCRIPT_MISSING"}

    proc = subprocess.run(
        ["python3", str(check_script), "--repo-root", str(target_root)],
        cwd=source_root,
        text=True,
        capture_output=True,
    )
    stdout_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    parsed: dict[str, Any] = {}
    if stdout_lines:
        try:
            candidate = json.loads(stdout_lines[-1])
            if isinstance(candidate, dict):
                parsed = candidate
        except Exception:
            parsed = {}

    return {
        "status": "OK" if proc.returncode == 0 and parsed.get("status") == "OK" else "FAIL",
        "returncode": proc.returncode,
        "payload": parsed,
        "stderr_preview": (proc.stderr or "").strip().splitlines()[:10],
    }


def _sync_target_repo(
    *,
    source_root: Path,
    target_root: Path,
    rel_paths: list[str],
    preserve_existing_paths: set[str],
    apply: bool,
    validate_after_sync: bool,
) -> dict[str, Any]:
    if not target_root.exists() or not target_root.is_dir():
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "TARGET_REPO_NOT_FOUND",
            "files": [],
        }

    file_results: list[dict[str, Any]] = []
    missing_source: list[str] = []
    write_errors: list[str] = []
    changed_count = 0

    for rel in rel_paths:
        src = (source_root / rel).resolve()
        dst = (target_root / rel).resolve()
        if not src.exists() or not src.is_file():
            missing_source.append(rel)
            continue

        src_hash = _sha256_file(src)
        dst_exists = dst.exists()
        dst_hash = _sha256_file(dst) if dst_exists and dst.is_file() else None

        if dst_exists and rel in preserve_existing_paths:
            action = "preserve_existing"
            file_results.append(
                {
                    "path": rel,
                    "action": action,
                    "source_sha256": src_hash,
                    "target_sha256_before": dst_hash,
                }
            )
            continue

        if dst_exists and dst_hash == src_hash:
            action = "no_change"
        elif apply:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                action = "updated" if dst_exists else "created"
                changed_count += 1
            except Exception as exc:
                write_errors.append(f"{rel}:{exc}")
                action = "error"
        else:
            action = "would_update" if dst_exists else "would_create"
            changed_count += 1

        file_results.append(
            {
                "path": rel,
                "action": action,
                "source_sha256": src_hash,
                "target_sha256_before": dst_hash,
            }
        )

    if missing_source:
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "SOURCE_FILES_MISSING",
            "missing_source_files": missing_source,
            "files": file_results,
        }

    if write_errors:
        return {
            "repo_root": str(target_root),
            "status": "FAIL",
            "reason": "WRITE_FAILED",
            "write_errors": write_errors,
            "files": file_results,
        }

    validation: dict[str, Any] | None = None
    if apply and validate_after_sync:
        validation = _run_standards_validation(source_root, target_root)

    status = "OK"
    if isinstance(validation, dict) and validation.get("status") != "OK":
        status = "FAIL"

    return {
        "repo_root": str(target_root),
        "status": status,
        "mode": "apply" if apply else "dry-run",
        "changed_files": changed_count,
        "files": file_results,
        "validation": validation,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        default="",
        help="Standards source repo root (default: current script parent repo).",
    )
    parser.add_argument(
        "--target-repo-root",
        action="append",
        default=[],
        help="Managed repo root (repeatable).",
    )
    parser.add_argument(
        "--manifest-path",
        default="",
        help="Optional managed repos manifest path (.cache/managed_repos.v1.json).",
    )
    parser.add_argument(
        "--output",
        default=".cache/reports/managed_repo_standards_sync/report.v1.json",
        help="Output report path (relative to source root if not absolute).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply sync to target repos. Default mode is dry-run.",
    )
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="Include source root if it is also listed as a target.",
    )
    parser.add_argument(
        "--validate-after-sync",
        action="store_true",
        help="Run standards.lock validation per target after apply.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    script_root = Path(__file__).resolve().parents[1]
    source_root = (
        Path(str(args.source_root).strip()).expanduser().resolve()
        if str(args.source_root).strip()
        else script_root
    )

    lock_path = source_root / "standards.lock"
    if not lock_path.exists():
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "STANDARDS_LOCK_MISSING",
                    "source_root": str(source_root),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    lock_obj = _load_json(lock_path)
    rel_paths = _collect_standard_paths(lock_obj)

    managed_repo_sync = lock_obj.get("managed_repo_sync")
    preserve_existing_paths: set[str] = set()
    if isinstance(managed_repo_sync, dict):
        raw_preserve = managed_repo_sync.get("preserve_existing_paths")
        if isinstance(raw_preserve, list):
            for item in raw_preserve:
                if isinstance(item, str) and item.strip():
                    preserve_existing_paths.add(_safe_relpath(item))

    targets: list[Path] = []
    for raw in args.target_repo_root:
        txt = str(raw).strip()
        if txt:
            targets.append(Path(txt).expanduser().resolve())

    manifest_arg = str(args.manifest_path).strip()
    if manifest_arg:
        manifest_path = Path(manifest_arg).expanduser().resolve()
        if not manifest_path.exists():
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "error_code": "MANIFEST_NOT_FOUND",
                        "manifest_path": str(manifest_path),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 2
        targets.extend(_load_manifest_targets(manifest_path))

    targets = _dedupe_paths(targets)
    if not args.include_self:
        targets = [p for p in targets if p != source_root]

    if not targets:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "TARGET_REPO_REQUIRED",
                    "message": "En az bir target repo gereklidir.",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    results = [
        _sync_target_repo(
            source_root=source_root,
            target_root=target,
            rel_paths=rel_paths,
            preserve_existing_paths=preserve_existing_paths,
            apply=bool(args.apply),
            validate_after_sync=bool(args.validate_after_sync),
        )
        for target in targets
    ]

    failed = [r for r in results if r.get("status") != "OK"]
    changed_total = sum(int(r.get("changed_files") or 0) for r in results if isinstance(r, dict))

    output_arg = str(args.output).strip()
    output_path = Path(output_arg)
    if not output_path.is_absolute():
        output_path = (source_root / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "version": "v1",
        "kind": "managed-repo-standards-sync-report",
        "generated_at": _now_iso_utc(),
        "source_root": str(source_root),
        "mode": "apply" if args.apply else "dry-run",
        "sync_paths": rel_paths,
        "preserve_existing_paths": sorted(preserve_existing_paths),
        "target_count": len(results),
        "changed_total": changed_total,
        "failed_count": len(failed),
        "results": results,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    status = "OK" if not failed else "FAIL"
    print(
        json.dumps(
            {
                "status": status,
                "mode": report["mode"],
                "target_count": report["target_count"],
                "changed_total": report["changed_total"],
                "failed_count": report["failed_count"],
                "report_path": str(output_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
