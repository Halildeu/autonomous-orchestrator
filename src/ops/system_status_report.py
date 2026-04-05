from __future__ import annotations
from src.shared.utils import write_text_atomic

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
from .drift_scoreboard import (
    build_drift_scoreboard,
    write_drift_scoreboard,
)

def _canonical_artifact_path(raw: str | Path, *, workspace_root: Path, core_root: Path) -> str:
    path = raw if isinstance(raw, Path) else Path(str(raw))
    if path.is_absolute():
        return str(path.resolve())
    workspace_candidate = (workspace_root / path).resolve()
    core_candidate = (core_root / path).resolve()
    if core_candidate.exists() and not workspace_candidate.exists():
        return str(core_candidate)
    return str(workspace_candidate)


def _system_status_policy_path(*, workspace_root: Path, core_root: Path) -> Path:
    ws_policy = workspace_root / "policies" / "policy_system_status.v1.json"
    if ws_policy.exists():
        return ws_policy.resolve()
    return (core_root / "policies" / "policy_system_status.v1.json").resolve()


def _system_status_source_artifact_paths(
    *,
    workspace_root: Path,
    core_root: Path,
    out_json: Path,
    out_md: Path,
    drift_scoreboard_path: str | Path,
) -> dict[str, str]:
    return {
        "policy_system_status": str(_system_status_policy_path(workspace_root=workspace_root, core_root=core_root)),
        "portfolio_status": str((workspace_root / ".cache" / "reports" / "portfolio_status.v1.json").resolve()),
        "roadmap_state": str((workspace_root / ".cache" / "roadmap_state.v1.json").resolve()),
        "work_intake": str((workspace_root / ".cache" / "index" / "work_intake.v1.json").resolve()),
        "extension_registry": str((workspace_root / ".cache" / "index" / "extension_registry.v1.json").resolve()),
        "active_context_profile": str((workspace_root / ".cache" / "index" / "active_context_profile.v1.json").resolve()),
        "system_status_json": str(out_json.resolve()),
        "system_status_md": str(out_md.resolve()),
        "drift_scoreboard": _canonical_artifact_path(
            drift_scoreboard_path,
            workspace_root=workspace_root,
            core_root=core_root,
        ),
    }


def _attach_provenance_notes(report: dict[str, Any], source_artifact_paths: dict[str, str]) -> None:
    notes = report.get("notes") if isinstance(report.get("notes"), list) else []
    note_values = [str(item) for item in notes if isinstance(item, str)]
    for key in sorted(source_artifact_paths):
        value = source_artifact_paths[key]
        if not value:
            continue
        note_values.append(f"source_artifact.{key}={value}")
    report["notes"] = list(dict.fromkeys(note_values))


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
    drift_payload = build_drift_scoreboard(
        workspace_root=workspace_root,
        core_root=core_root,
        managed_repo_standards_summary=report.get("sections", {}).get("managed_repo_standards")
        if isinstance(report.get("sections"), dict)
        else None,
        max_repos=200,
    )
    drift_report_path = _canonical_artifact_path(
        drift_payload.get("report_path") or "",
        workspace_root=workspace_root,
        core_root=core_root,
    )
    source_artifact_paths = _system_status_source_artifact_paths(
        workspace_root=workspace_root,
        core_root=core_root,
        out_json=out_json,
        out_md=out_md,
        drift_scoreboard_path=drift_report_path,
    )
    _attach_provenance_notes(report, source_artifact_paths)
    errors = _validate_schema(core_root, report)
    if errors:
        return {
            "status": "FAIL",
            "error_code": "SCHEMA_INVALID",
            "errors": errors[:10],
            "out_json": str(out_json),
            "out_md": str(out_md),
            "drift_scoreboard_path": drift_report_path,
            "source_artifact_paths": source_artifact_paths,
            "on_fail": policy.on_fail,
        }

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "overall_status": report.get("overall_status"),
            "out_json": str(out_json),
            "out_md": str(out_md),
            "drift_scoreboard_path": drift_report_path,
            "source_artifact_paths": source_artifact_paths,
            "on_fail": policy.on_fail,
        }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_json, _dump_json(report))
    write_text_atomic(out_md, _render_md(report))
    write_drift_scoreboard(workspace_root=workspace_root, scoreboard=drift_payload)

    return {
        "status": "OK",
        "overall_status": report.get("overall_status"),
        "out_json": str(out_json),
        "out_md": str(out_md),
        "drift_scoreboard_path": drift_report_path,
        "source_artifact_paths": source_artifact_paths,
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
