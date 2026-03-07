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

    ws = repo_root / ".cache" / "ws_system_status_error_observability_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "module_delivery_lanes" / "integration.v1.json",
        {
            "version": "v1",
            "kind": "module-delivery-lane-report",
            "lane": "integration",
            "status": "FAIL",
            "started_at": "2026-03-07T12:10:00Z",
            "finished_at": "2026-03-07T12:11:00Z",
            "return_code": 1,
            "timed_out": False,
            "stdout_tail": ["integration start"],
            "stderr_tail": ["integration failed"],
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json",
        {
            "version": "v1",
            "status": "WARN",
            "generated_at": "2026-03-07T12:12:00Z",
            "events_path": ".cache/reports/cockpit_frontend_telemetry.v1.jsonl",
            "total_events": 1,
            "runtime_error_count": 0,
            "console_error_count": 1,
            "unhandled_rejection_count": 0,
            "last_event_at": "2026-03-07T12:12:00Z",
            "last_event_type": "console_error",
            "last_message": "console broke",
        },
    )
    telemetry_events = ws / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl"
    telemetry_events.parent.mkdir(parents=True, exist_ok=True)
    telemetry_events.write_text(
        json.dumps(
            {
                "version": "v1",
                "ts": "2026-03-07T12:12:00Z",
                "event_type": "console_error",
                "message": "console broke",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    surface = sections.get("error_observability") if isinstance(sections, dict) else None
    if not isinstance(surface, dict):
        raise SystemExit("system_status_error_observability_surface_contract_test failed: section missing")
    if str(surface.get("status") or "") != "WARN":
        raise SystemExit("system_status_error_observability_surface_contract_test failed: status mismatch")
    if int(surface.get("items_total") or 0) != 2:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: total mismatch")
    if int(surface.get("active_items_total") or 0) != 2:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: active total mismatch")
    if int(surface.get("acked_items_total") or 0) != 0:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: acked total mismatch")
    if str(surface.get("latest_source_type") or "") != "browser":
        raise SystemExit("system_status_error_observability_surface_contract_test failed: latest source mismatch")
    if str(surface.get("report_path") or "") != ".cache/reports/error_observability.v1.json":
        raise SystemExit("system_status_error_observability_surface_contract_test failed: report path mismatch")

    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)
    summary = ui_payload.get("error_observability_summary") if isinstance(ui_payload, dict) else None
    if not isinstance(summary, dict):
        raise SystemExit("system_status_error_observability_surface_contract_test failed: ui summary missing")
    if int(summary.get("browser_count") or 0) != 1:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: ui browser count mismatch")
    if int(summary.get("active_items_total") or 0) != 2:
        raise SystemExit("system_status_error_observability_surface_contract_test failed: ui active total mismatch")
    if str(summary.get("latest_source_type") or "") != "browser":
        raise SystemExit("system_status_error_observability_surface_contract_test failed: ui latest source mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
