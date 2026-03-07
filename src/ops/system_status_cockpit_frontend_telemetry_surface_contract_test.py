from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_system_status_cockpit_frontend_telemetry_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "cockpit_healthcheck.v1.json",
        {"version": "v1", "status": "OK", "port": 8787, "request_id": "REQ-123"},
    )
    _write_json(
        ws / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json",
        {
            "version": "v1",
            "status": "WARN",
            "generated_at": "2026-03-07T11:05:00Z",
            "events_path": ".cache/reports/cockpit_frontend_telemetry.v1.jsonl",
            "total_events": 3,
            "runtime_error_count": 1,
            "console_error_count": 1,
            "unhandled_rejection_count": 1,
            "last_event_at": "2026-03-07T11:04:59Z",
            "last_event_type": "runtime_error",
            "last_message": "UI runtime crash",
        },
    )

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: missing system status path"
        )
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    cockpit = sections.get("cockpit_lite") if isinstance(sections, dict) else None
    if not isinstance(cockpit, dict):
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: cockpit_lite missing"
        )
    if str(cockpit.get("frontend_telemetry_status") or "") != "WARN":
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: telemetry status mismatch"
        )
    if int(cockpit.get("frontend_runtime_error_count") or 0) != 1:
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: runtime count mismatch"
        )
    if str(cockpit.get("last_frontend_telemetry_events_path") or "") != ".cache/reports/cockpit_frontend_telemetry.v1.jsonl":
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: events path mismatch"
        )
    if str(cockpit.get("last_frontend_event_type") or "") != "runtime_error":
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: last event type mismatch"
        )

    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)
    summary = ui_payload.get("cockpit_frontend_telemetry_summary") if isinstance(ui_payload, dict) else None
    if not isinstance(summary, dict):
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: ui snapshot summary missing"
        )
    if str(summary.get("status") or "") != "WARN":
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: ui snapshot status mismatch"
        )
    if str(summary.get("last_event_type") or "") != "runtime_error":
        raise SystemExit(
            "system_status_cockpit_frontend_telemetry_surface_contract_test failed: ui snapshot last event mismatch"
        )

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
