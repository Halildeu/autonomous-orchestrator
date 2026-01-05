from __future__ import annotations

import argparse
import json
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


def _repo_root() -> Path:
    # src/tenant/build_formats_index.py -> repo root
    return Path(__file__).resolve().parents[2]


def _discover_format_sources(*, workspace_root: Path) -> tuple[list[Path], list[Path]]:
    ws = workspace_root.resolve()
    core_root = _repo_root()
    ws_dir = ws / "formats"
    core_dir = core_root / "formats"

    ws_paths: list[Path] = []
    if ws_dir.exists() and ws_dir.is_dir():
        for p in sorted(ws_dir.glob("*.v1.json"), key=lambda x: x.as_posix()):
            if p.is_file():
                ws_paths.append(p)

    core_paths: list[Path] = []
    if core_dir.exists() and core_dir.is_dir():
        for p in sorted(core_dir.glob("*.v1.json"), key=lambda x: x.as_posix()):
            if p.is_file():
                core_paths.append(p)

    return (ws_paths, core_paths)


def _build_formats_index(*, workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    ws = workspace_root.resolve()
    warnings: list[str] = []

    ws_paths, core_paths = _discover_format_sources(workspace_root=ws)

    # id -> {id, version, source}; workspace overrides core by id.
    chosen: dict[str, dict[str, Any]] = {}

    def ingest(path: Path, *, source: str) -> None:
        rel = None
        try:
            rel = path.relative_to(ws).as_posix()
        except Exception:
            rel = path.as_posix()
        try:
            obj = _load_json(path)
        except Exception:
            warnings.append("FORMAT_JSON_INVALID:" + rel)
            return
        if not isinstance(obj, dict):
            warnings.append("FORMAT_JSON_INVALID:" + rel)
            return
        fmt_id = obj.get("id")
        if not isinstance(fmt_id, str) or not fmt_id.strip():
            warnings.append("FORMAT_MISSING_ID:" + rel)
            return
        ver = obj.get("version")
        if not isinstance(ver, str) or not ver.strip():
            ver = "unknown"

        if fmt_id in chosen:
            prev = chosen.get(fmt_id) if isinstance(chosen.get(fmt_id), dict) else {}
            prev_source = prev.get("source")
            if source == "core":
                # Core duplicate; keep first by path ordering.
                warnings.append("FORMAT_DUPLICATE_ID_CORE:" + fmt_id)
                return
            if source == "workspace" and prev_source == "workspace":
                # Workspace duplicate; keep first by path ordering.
                warnings.append("FORMAT_DUPLICATE_ID_WORKSPACE:" + fmt_id)
                return
            # Workspace overrides core deterministically by id.
            if source == "workspace" and prev_source == "core":
                warnings.append("FORMAT_OVERRIDDEN_BY_WORKSPACE:" + fmt_id)
        chosen[fmt_id] = {"id": fmt_id, "version": str(ver), "source": source}

    for p in core_paths:
        ingest(p, source="core")
    for p in ws_paths:
        ingest(p, source="workspace")

    formats = sorted(chosen.values(), key=lambda x: str(x.get("id") or ""))

    index_obj: dict[str, Any] = {
        "version": "v1",
        "workspace_root": str(ws),
        "formats": formats,
        "warnings": warnings,
    }
    return (index_obj, warnings)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.tenant.build_formats_index", add_help=True)
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

    out_path = Path(str(args.out)) if args.out is not None else (ws / ".cache" / "index" / "formats.v1.json")
    out_path = out_path.resolve()

    index_obj, warnings = _build_formats_index(workspace_root=ws)
    payload = _dump_json(index_obj)
    bytes_estimate = len(payload.encode("utf-8"))
    formats_found = len(index_obj.get("formats") or []) if isinstance(index_obj.get("formats"), list) else 0

    if dry_run:
        print(
            json.dumps(
                {
                    "status": "WOULD_WRITE",
                    "out": str(out_path),
                    "bytes_estimate": int(bytes_estimate),
                    "formats_found": int(formats_found),
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
                {"status": "FAIL", "error_code": "WRITE_MISSING", "message": "formats index not found after write", "out": str(out_path)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            {"status": "OK", "out": str(out_path), "formats_found": int(formats_found), "warnings_count": int(len(warnings))},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
