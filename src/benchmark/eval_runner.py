from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.integrity_utils import load_policy_integrity


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _write_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _ensure_catalogs(workspace_root: Path, *, allow_write: bool) -> tuple[Path, Path, int, int]:
    bp_path = workspace_root / ".cache" / "index" / "bp_catalog.v1.json"
    trend_path = workspace_root / ".cache" / "index" / "trend_catalog.v1.json"

    bp_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": [],
    }
    trend_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": [],
    }
    if allow_write:
        _write_if_missing(bp_path, bp_payload)
        _write_if_missing(trend_path, trend_payload)

    bp_items = 0
    trend_items = 0
    if bp_path.exists():
        try:
            obj = _load_json(bp_path)
            items = obj.get("items") if isinstance(obj, dict) else None
            bp_items = len(items) if isinstance(items, list) else 0
        except Exception:
            bp_items = 0
    if trend_path.exists():
        try:
            obj = _load_json(trend_path)
            items = obj.get("items") if isinstance(obj, dict) else None
            trend_items = len(items) if isinstance(items, list) else 0
        except Exception:
            trend_items = 0

    return bp_path, trend_path, bp_items, trend_items


def run_eval(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    _ensure_inside_workspace(workspace_root, eval_path)

    bp_path, trend_path, bp_items, trend_items = _ensure_catalogs(workspace_root, allow_write=not dry_run)

    notes: list[str] = []
    report_only = False
    status = "OK"
    controls = 0
    metrics = 0
    integrity_snapshot_ref = str(Path(".cache") / "reports" / "integrity_verify.v1.json")

    raw_ref = str(Path(".cache") / "index" / "assessment_raw.v1.json")
    if raw_path.exists():
        try:
            raw = _load_json(raw_path)
            inputs = raw.get("inputs") if isinstance(raw, dict) else None
            controls = int(inputs.get("controls") or 0) if isinstance(inputs, dict) else 0
            metrics = int(inputs.get("metrics") or 0) if isinstance(inputs, dict) else 0
            ref = raw.get("integrity_snapshot_ref") if isinstance(raw, dict) else None
            if isinstance(ref, str) and ref.strip():
                integrity_snapshot_ref = ref
        except Exception:
            status = "WARN"
            notes.append("invalid_raw")
    else:
        status = "SKIPPED"
        report_only = True
        notes.append("raw_missing")

    integrity_status = None
    integrity_path = workspace_root / integrity_snapshot_ref
    if integrity_path.exists():
        try:
            obj = _load_json(integrity_path)
            integrity_status = obj.get("verify_on_read_result") if isinstance(obj, dict) else None
        except Exception:
            integrity_status = None
    else:
        integrity_status = "FAIL"
        notes.append("integrity_snapshot_missing")

    policy = load_policy_integrity(core_root=core_root, workspace_root=workspace_root)
    allow_report_only = bool(policy.get("allow_report_only_when_missing_sources", True))
    if integrity_status == "FAIL":
        if allow_report_only:
            status = "WARN" if status != "SKIPPED" else status
            report_only = True
            notes.append("integrity_report_only")
        else:
            status = "SKIPPED"
            report_only = True
            notes.append("integrity_blocked")

    total = controls + metrics
    maturity_avg = 0.0
    coverage = 0.0 if total <= 0 else min(1.0, float(bp_items + trend_items) / float(total))

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "report_only": bool(report_only),
        "integrity_snapshot_ref": str(integrity_snapshot_ref),
        "raw_ref": str(raw_ref),
        "bp_catalog_ref": str(Path(".cache") / "index" / "bp_catalog.v1.json"),
        "trend_catalog_ref": str(Path(".cache") / "index" / "trend_catalog.v1.json"),
        "scores": {"maturity_avg": round(maturity_avg, 4), "coverage": round(coverage, 4)},
        "inputs": {"controls": controls, "metrics": metrics, "bp_items": bp_items, "trend_items": trend_items},
        "notes": sorted(set(notes)),
    }

    schema_path = core_root / "schemas" / "assessment-eval.schema.v1.json"
    if schema_path.exists():
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(payload)

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "out": str(eval_path),
            "report_only": report_only,
        }

    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "OK",
        "out": str(eval_path),
        "report_only": report_only,
    }
