from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from .system_status_builder import (
    _dump_json,
    _load_policy,
    _parse_bool,
    _repo_root,
    _render_md,
    _resolve_workspace_path,
    _validate_schema,
    build_system_status,
)

def run_system_status(*, workspace_root: Path, core_root: Path, dry_run: bool) -> dict[str, Any]:
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        return {"status": "OK", "note": "POLICY_DISABLED", "on_fail": policy.on_fail}

    out_json = _resolve_workspace_path(workspace_root, policy.out_json)
    out_md = _resolve_workspace_path(workspace_root, policy.out_md)
    if out_json is None or out_md is None:
        return {"status": "FAIL", "error_code": "OUTPUT_PATH_INVALID", "on_fail": policy.on_fail}

    report = build_system_status(
        workspace_root=workspace_root,
        core_root=core_root,
        policy=policy,
        dry_run=dry_run,
    )
    errors = _validate_schema(core_root, report)
    if errors:
        return {"status": "FAIL", "error_code": "SCHEMA_INVALID", "errors": errors[:10], "out_json": str(out_json), "out_md": str(out_md), "on_fail": policy.on_fail}

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "overall_status": report.get("overall_status"),
            "out_json": str(out_json),
            "out_md": str(out_md),
            "on_fail": policy.on_fail,
        }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")

    return {
        "status": "OK",
        "overall_status": report.get("overall_status"),
        "out_json": str(out_json),
        "out_md": str(out_md),
        "on_fail": policy.on_fail,
    }


def action_from_system_status_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    overall = result.get("overall_status")
    out_json = result.get("out_json") if isinstance(result.get("out_json"), str) else None
    title = "System status report generated"
    if status == "FAIL":
        title = "System status report failed"
    severity = "INFO" if status in {"OK", "WOULD_WRITE"} else "WARN"
    action_kind = "SYSTEM_STATUS" if status in {"OK", "WOULD_WRITE"} else "SYSTEM_STATUS_FAIL"
    msg = f"System status: {overall}" if overall else "System status report generated"
    action_id = sha256(f"SYSTEM_STATUS|{status}|{out_json}".encode("utf-8")).hexdigest()[:16]
    return {
        "action_id": action_id,
        "severity": severity,
        "kind": action_kind,
        "milestone_hint": "M8.1",
        "source": "SYSTEM_STATUS",
        "title": title,
        "details": {
            "status": status,
            "overall_status": overall,
            "out_json": out_json,
            "out_md": result.get("out_md"),
            "error_code": result.get("error_code"),
        },
        "message": msg,
        "resolved": status in {"OK", "WOULD_WRITE"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.system_status_report", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "OK", "note": "POLICY_DISABLED"}, ensure_ascii=False, sort_keys=True))
        return 0

    res = run_system_status(workspace_root=workspace_root, core_root=core_root, dry_run=dry_run)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
