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

    ws = repo_root / ".cache" / "ws_system_status_module_delivery_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    lane_dir = ws / ".cache" / "reports" / "module_delivery_lanes"
    _write_json(
        lane_dir / "unit.v1.json",
        {
            "version": "v1",
            "kind": "module-delivery-lane-report",
            "lane": "unit",
            "status": "OK",
            "started_at": "2026-03-07T09:00:00Z",
            "finished_at": "2026-03-07T09:01:00Z",
            "duration_ms": 60000,
            "return_code": 0,
            "timed_out": False,
            "timeout_seconds": 900,
            "command": "pytest tests/unit",
            "config_path": str(repo_root / "ci" / "module_delivery_lanes.v1.json"),
            "stdout_tail": ["unit pass"],
            "stderr_tail": [],
        },
    )
    _write_json(
        lane_dir / "contract.v1.json",
        {
            "version": "v1",
            "kind": "module-delivery-lane-report",
            "lane": "contract",
            "status": "FAIL",
            "started_at": "2026-03-07T09:02:00Z",
            "finished_at": "2026-03-07T09:03:00Z",
            "duration_ms": 60000,
            "return_code": 2,
            "timed_out": False,
            "timeout_seconds": 900,
            "command": "python ci/validate_schemas.py",
            "config_path": str(repo_root / "ci" / "module_delivery_lanes.v1.json"),
            "stdout_tail": ["schema run start", "schema run fail"],
            "stderr_tail": ["validation error", "missing field"],
        },
    )

    sys_result = run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    report_path = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: missing system status path")
    report = _load_json(Path(report_path))
    sections = report.get("sections") if isinstance(report, dict) else {}
    module_delivery = sections.get("module_delivery") if isinstance(sections, dict) else None
    if not isinstance(module_delivery, dict):
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: missing module_delivery section")
    if str(module_delivery.get("status")) != "FAIL":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: status mismatch")
    if int(module_delivery.get("lanes_total") or 0) != 2:
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: lanes_total mismatch")
    if int(module_delivery.get("lanes_ok") or 0) != 1:
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: lanes_ok mismatch")
    if int(module_delivery.get("lanes_fail") or 0) != 1:
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: lanes_fail mismatch")
    if str(module_delivery.get("last_failed_lane") or "") != "contract":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: failed lane mismatch")
    if str(module_delivery.get("last_failed_report_path") or "") != ".cache/reports/module_delivery_lanes/contract.v1.json":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: failed report path mismatch")
    if int(module_delivery.get("last_failed_return_code") or 0) != 2:
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: return code mismatch")
    if str(module_delivery.get("last_failed_stderr_preview") or "") != "validation error\nmissing field":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: stderr preview mismatch")

    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)
    summary = ui_payload.get("module_delivery_summary") if isinstance(ui_payload, dict) else None
    if not isinstance(summary, dict):
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: ui summary missing")
    if str(summary.get("status") or "") != "FAIL":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: ui status mismatch")
    if str(summary.get("last_failed_lane") or "") != "contract":
        raise SystemExit("system_status_module_delivery_surface_contract_test failed: ui failed lane mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
