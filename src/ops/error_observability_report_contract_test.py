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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.error_observability_report import run_error_observability

    ws = repo_root / ".cache" / "ws_error_observability_report"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "module_delivery_lanes" / "contract.v1.json",
        {
            "version": "v1",
            "kind": "module-delivery-lane-report",
            "lane": "contract",
            "status": "FAIL",
            "started_at": "2026-03-07T12:00:00Z",
            "finished_at": "2026-03-07T12:01:00Z",
            "return_code": 2,
            "timed_out": False,
            "stdout_tail": ["schema start"],
            "stderr_tail": ["schema fail"],
        },
    )
    evidence_dir = ws / "evidence" / "RUN-123"
    _write_json(
        evidence_dir / "summary.json",
        {
            "run_id": "RUN-123",
            "workflow_id": "wf.contract",
            "status": "FAILED",
            "result_state": "FAILED",
            "finished_at": "2026-03-07T12:02:00Z",
            "error_code": "POLICY_VIOLATION",
            "error": "workflow blocked",
            "failed_stderr_preview": "runner stderr",
        },
    )
    telemetry_events = ws / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl"
    telemetry_events.parent.mkdir(parents=True, exist_ok=True)
    telemetry_events.write_text(
        json.dumps(
            {
                "version": "v1",
                "ts": "2026-03-07T12:03:00Z",
                "event_type": "runtime_error",
                "message": "frontend crash",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        ws / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json",
        {
            "version": "v1",
            "status": "WARN",
            "generated_at": "2026-03-07T12:03:00Z",
            "events_path": ".cache/reports/cockpit_frontend_telemetry.v1.jsonl",
            "total_events": 1,
            "runtime_error_count": 1,
            "console_error_count": 0,
            "unhandled_rejection_count": 0,
            "last_event_at": "2026-03-07T12:03:00Z",
            "last_event_type": "runtime_error",
            "last_message": "frontend crash",
        },
    )

    report = run_error_observability(workspace_root=ws)
    if str(report.get("status") or "") != "WARN":
        raise SystemExit("error_observability_report_contract_test failed: status mismatch")
    if int(report.get("items_total") or 0) != 3:
        raise SystemExit("error_observability_report_contract_test failed: total mismatch")
    if int(report.get("build_count") or 0) != 1:
        raise SystemExit("error_observability_report_contract_test failed: build count mismatch")
    if int(report.get("runner_count") or 0) != 1:
        raise SystemExit("error_observability_report_contract_test failed: runner count mismatch")
    if int(report.get("browser_count") or 0) != 1:
        raise SystemExit("error_observability_report_contract_test failed: browser count mismatch")
    if int(report.get("active_items_total") or 0) != 3:
        raise SystemExit("error_observability_report_contract_test failed: active total mismatch")
    if int(report.get("acked_items_total") or 0) != 0:
        raise SystemExit("error_observability_report_contract_test failed: acked total mismatch")
    if str(report.get("ack_state_path") or "") != "":
        raise SystemExit("error_observability_report_contract_test failed: ack state path mismatch")
    if str(report.get("latest_source_type") or "") != "browser":
        raise SystemExit("error_observability_report_contract_test failed: latest source mismatch")
    if str(report.get("report_path") or "") != ".cache/reports/error_observability.v1.json":
        raise SystemExit("error_observability_report_contract_test failed: report path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
