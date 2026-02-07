from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / ".cache" / "ws_customer_default" / ".cache" / "ops" / "codex_dashboard_build.v1.py"
    if not script.exists():
        raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: script missing")

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        reports = ws_root / ".cache" / "reports"

        _write_json(
            reports / "codex_timeline_summary.v1.json",
            {
                "generated_at": _iso_now(),
                "status": "OK",
                "detail": {
                    "stats": {"pending_calls_count": 0, "stuck_calls_count": 0},
                    "tool_call_summary": {"completed_total_ms": 0, "completed_by_tool": [], "pending_by_tool": []},
                    "tool_calls": {"completed_top": [], "pending_top": [], "stuck_top": []},
                    "selected_rollout": {"path": ""},
                    "timeline": [],
                    "recent_rollouts": [],
                },
            },
        )
        _write_json(
            reports / "latency_watchdog.v1.json",
            {
                "generated_at": _iso_now(),
                "status": "OK",
                "op_latency": {
                    "pairs": {
                        "orphan_results": 0,
                        "pairs_count": 2,
                        "running_count": 0,
                        "pairing_mode_counts": {"call_id": 2, "result_for_seq": 0, "legacy": 0, "orphan": 0},
                        "call_id_coverage": {
                            "op_call_total": 2,
                            "op_call_with_call_id": 2,
                            "op_call_with_call_id_ratio": 1.0,
                            "result_total": 2,
                            "result_with_call_id": 2,
                            "result_with_call_id_ratio": 1.0,
                            "result_with_result_for_seq": 2,
                            "result_with_result_for_seq_ratio": 1.0,
                        },
                    },
                    "running_ops_stuck": [],
                    "running_ops_top": [],
                    "slow_ops_top": [],
                    "summary": {"by_op": [], "by_extension": []},
                },
                "hotspots": [],
            },
        )
        _write_json(
            reports / "extension_usage_summary.v1.json",
            {"generated_at": _iso_now(), "status": "OK", "counts": {"total_calls": 2, "unique_ops": 1}, "top_extensions": []},
        )
        _write_json(
            reports / "reaper_report.v1.json",
            {"cache": {"candidates": 0}, "dlq": {"candidates": 0}, "evidence": {"candidates": 0}},
        )

        cmd = [sys.executable, str(script), "--ws", str(ws_root)]
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: builder rc != 0")

        out_json = reports / "codex_dashboard.v1.json"
        out_html = reports / "codex_dashboard.v1.v1.html"
        if not out_json.exists():
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: dashboard json missing")
        if not out_html.exists():
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: dashboard html missing")

        dashboard = json.loads(out_json.read_text(encoding="utf-8"))
        lw = dashboard.get("latency_watchdog") if isinstance(dashboard.get("latency_watchdog"), dict) else {}
        if str(lw.get("p3b_status") or "") != "OK":
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: p3b_status expected OK")
        if not isinstance(lw.get("pairing_mode_counts"), dict):
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: pairing_mode_counts missing")
        if not isinstance(lw.get("call_id_coverage"), dict):
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: call_id_coverage missing")

        html = out_html.read_text(encoding="utf-8", errors="ignore")
        if "P3B Telemetry" not in html:
            raise SystemExit("codex_dashboard_p3b_telemetry_contract_test failed: telemetry card token missing")


if __name__ == "__main__":
    main()
