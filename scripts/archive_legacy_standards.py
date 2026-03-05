#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEGACY_SOURCES: tuple[tuple[str, str], ...] = (
    ("coding_standards_md", "docs/OPERATIONS/CODING-STANDARDS.md"),
    ("architecture_constraints_md", "docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md"),
    ("repo_layout_json", "docs/OPERATIONS/repo-layout.v1.json"),
    ("multi_repo_operating_contract_md", "docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md"),
)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", default="docs/ARCHIVE/legacy_standards")
    parser.add_argument(
        "--manifest-path",
        default="registry/archives/legacy_standards_archive.aistd.v1.json",
    )
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()

    snapshot_id = str(args.snapshot_id or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_root_rel = str(args.archive_root).strip()
    manifest_rel = str(args.manifest_path).strip()
    archive_root = (root / archive_root_rel).resolve()
    manifest_path = (root / manifest_rel).resolve()

    archive_base = archive_root / snapshot_id
    archive_base.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    missing: list[str] = []

    for source_id, source_rel in LEGACY_SOURCES:
        src = (root / source_rel).resolve()
        if not src.exists() or not src.is_file():
            missing.append(source_rel)
            continue

        dst = (archive_base / source_rel).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        src_hash = _sha256_file(src)
        dst_hash = _sha256_file(dst)
        if src_hash != dst_hash:
            raise RuntimeError(f"archive hash mismatch for {source_rel}")

        items.append(
            {
                "source_id": source_id,
                "source_path": source_rel,
                "archived_path": dst.relative_to(root).as_posix(),
                "sha256_source": src_hash,
                "sha256_archive": dst_hash,
                "status": "ARCHIVED",
            }
        )

    if missing and not bool(args.allow_missing):
        payload = {
            "status": "FAIL",
            "error_code": "LEGACY_SOURCE_MISSING",
            "missing_sources": missing,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    manifest = {
        "version": "v1",
        "kind": "legacy-standards-archive-aistd",
        "generated_at": _now_iso_utc(),
        "archive_root": archive_root_rel,
        "snapshot_id": snapshot_id,
        "items": items,
        "missing_sources": missing,
        "notes": [
            "legacy kaynaklar read-only archive olarak saklanir.",
            "normatif standart artik registry/technical_baseline.aistd.v1.json dosyasidir.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    payload = {
        "status": "WARN" if missing else "OK",
        "snapshot_id": snapshot_id,
        "archived_count": len(items),
        "missing_count": len(missing),
        "manifest_path": manifest_path.relative_to(root).as_posix(),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
