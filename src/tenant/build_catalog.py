from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _build_catalog(*, workspace_root: Path) -> tuple[dict[str, Any], list[str], bool]:
    ws = workspace_root.resolve()
    warnings: list[str] = []

    tenant_id = "TENANT-DEFAULT"

    decision_bundle_path = ws / "tenant" / tenant_id / "decision-bundle.v1.json"
    decision_bundle_present = decision_bundle_path.exists()
    if decision_bundle_present:
        try:
            _ = _load_json(decision_bundle_path)
        except Exception:
            warnings.append("DECISION_BUNDLE_INVALID")
    else:
        warnings.append("DECISION_BUNDLE_MISSING")

    packs_dir = ws / "packs"
    pack_manifest_paths: list[Path] = []
    if packs_dir.exists() and packs_dir.is_dir():
        for p in sorted(packs_dir.glob("*/manifest.v1.json"), key=lambda x: x.as_posix()):
            if p.is_file():
                pack_manifest_paths.append(p)

    packs: list[dict[str, Any]] = []
    for mp in pack_manifest_paths:
        rel = mp.relative_to(ws).as_posix()
        try:
            obj = _load_json(mp)
        except Exception:
            warnings.append("PACK_MANIFEST_INVALID:" + rel)
            continue
        if not isinstance(obj, dict):
            warnings.append("PACK_MANIFEST_INVALID:" + rel)
            continue

        pack_id = obj.get("pack_id")
        if not isinstance(pack_id, str) or not pack_id.strip():
            warnings.append("PACK_MANIFEST_MISSING_PACK_ID:" + rel)
            continue

        pack_version = obj.get("version")
        if not isinstance(pack_version, str) or not pack_version.strip():
            pack_version = "unknown"

        applies_to = obj.get("applies_to") if isinstance(obj.get("applies_to"), dict) else {}
        provides = obj.get("provides") if isinstance(obj.get("provides"), dict) else {}

        packs.append(
            {
                "pack_id": str(pack_id),
                "version": str(pack_version),
                "applies_to": applies_to,
                "provides": provides,
            }
        )

    packs.sort(key=lambda x: str(x.get("pack_id") or ""))

    catalog_obj: dict[str, Any] = {
        "version": "v1",
        "workspace_root": str(ws),
        "tenant": tenant_id,
        "decision_bundle_present": bool(decision_bundle_present),
        "packs": packs,
        "warnings": warnings,
    }
    return (catalog_obj, warnings, bool(decision_bundle_present))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.tenant.build_catalog", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "INVALID_DRY_RUN", "message": "expected --dry-run true|false"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    workspace_root = Path(str(args.workspace_root))
    ws = workspace_root.resolve()
    if not ws.exists() or not ws.is_dir():
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID", "message": str(ws)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    out_path = Path(str(args.out)) if args.out is not None else (ws / ".cache" / "index" / "catalog.v1.json")
    out_path = out_path.resolve()

    catalog_obj, warnings, decision_bundle_present = _build_catalog(workspace_root=ws)
    payload = _dump_json(catalog_obj)
    bytes_estimate = len(payload.encode("utf-8"))

    if dry_run:
        print(
            json.dumps(
                {
                    "status": "WOULD_WRITE",
                    "out": str(out_path),
                    "bytes_estimate": int(bytes_estimate),
                    "packs_found": int(len(catalog_obj.get("packs") or [])),
                    "decision_bundle_present": bool(decision_bundle_present),
                    "warnings_count": int(len(warnings)),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    except Exception as e:
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "WRITE_FAILED", "message": str(e)[:300], "out": str(out_path)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    if not out_path.exists():
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "WRITE_MISSING", "message": "catalog file not found after write", "out": str(out_path)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            {"status": "OK", "out": str(out_path), "packs_found": int(len(catalog_obj.get("packs") or [])), "warnings_count": int(len(warnings))},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

