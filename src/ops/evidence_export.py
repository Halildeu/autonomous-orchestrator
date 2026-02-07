from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evidence.integrity_verify import verify_run_dir


EXPORT_README_NAME = "EXPORT_README.txt"


def parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError("Expected boolean value true|false.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reason_for_integrity(status: str) -> str:
    if status == "MISSING":
        return "INTEGRITY_MISSING"
    return "INTEGRITY_MISMATCH"


def export_evidence_zip(*, run_dir: Path, out_zip: Path, force: bool = False) -> tuple[int, dict[str, Any]]:
    run_dir = run_dir.resolve()
    run_id = run_dir.name

    if not run_dir.exists() or not run_dir.is_dir():
        return (
            2,
            {
                "status": "FAIL",
                "reason": "RUN_DIR_NOT_FOUND",
                "run_id": run_id,
            },
        )

    integrity_payload = verify_run_dir(run_dir)
    integrity_status = integrity_payload.get("status")
    integrity_status = integrity_status if integrity_status in {"OK", "MISSING", "MISMATCH"} else "MISMATCH"

    if integrity_status != "OK" and not force:
        return (
            2,
            {
                "status": "FAIL",
                "reason": _reason_for_integrity(integrity_status),
                "run_id": run_id,
                "integrity": integrity_status,
            },
        )

    out_zip = out_zip.resolve() if out_zip.is_absolute() else (Path.cwd() / out_zip).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        if not force:
            return (
                2,
                {
                    "status": "FAIL",
                    "reason": "OUT_EXISTS",
                    "run_id": run_id,
                    "out": str(out_zip),
                },
            )
        out_zip.unlink()

    readme = "\n".join(
        [
            "Evidence export (zip)",
            "",
            f"run_id: {run_id}",
            f"export_time: {_now_iso()}",
            f"integrity_status: {integrity_status}",
            "",
            "How to verify after unzip:",
            "  python -m src.evidence.integrity_verify --run <unzipped_dir>",
            "",
        ]
    )

    file_paths = [p for p in run_dir.rglob("*") if p.is_file()]
    file_paths.sort(key=lambda p: p.relative_to(run_dir).as_posix())

    with zipfile.ZipFile(out_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(EXPORT_README_NAME, readme)
        for p in file_paths:
            arcname = p.relative_to(run_dir).as_posix()
            zf.write(p, arcname)

    size = int(out_zip.stat().st_size) if out_zip.exists() else 0
    payload: dict[str, Any] = {
        "status": "OK",
        "run_id": run_id,
        "out": str(out_zip),
        "bytes": size,
        "integrity": integrity_status,
    }
    return (0, payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.evidence_export")
    ap.add_argument("--run", required=True, help="Path to evidence/<run_id> directory.")
    ap.add_argument("--out", required=True, help="Output zip path.")
    ap.add_argument("--force", default="false", help="true|false (default: false).")
    args = ap.parse_args(argv)

    try:
        force = parse_bool(str(args.force))
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    code, payload = export_evidence_zip(run_dir=Path(str(args.run)), out_zip=Path(str(args.out)), force=force)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())

