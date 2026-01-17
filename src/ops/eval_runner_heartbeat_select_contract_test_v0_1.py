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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.eval_runner_heartbeat_select import run_eval_runner_heartbeat_select

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "eval_runner_heartbeat_select_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    reports = ws_root / ".cache" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    pinpoint_payload = {
        "version": "v1",
        "eval_runner_read_path": ".cache/airunner/airrunner_heartbeat.v1.json",
        "eval_runner_read_key": "last_tick_at",
        "results": [
            {
                "path": "src/benchmark/eval_runner.py",
                "contexts": [
                    {
                        "hit_line": 10,
                        "snippet": "hb_path = '.cache/reports/other_heartbeat.v1.json'\\n"
                        "key = 'last_tick_at'\\n"
                        "threshold_ref = 'heartbeat_stale_seconds_warn'",
                    }
                ],
            }
        ],
        "candidate_input_keys": ["updated_at", "last_tick_at"],
        "other_path": "logs/heartbeat_trace.v1.json",
    }
    pinpoint_path = reports / "eval_runner_heartbeat_pinpoint.v1.json"
    _write_json(pinpoint_path, pinpoint_payload)

    result = run_eval_runner_heartbeat_select(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        out_path=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = reports / "eval_runner_heartbeat_exact_selection.v1.json"
    _assert(out_json.exists(), "output not written")
    out_payload = json.loads(out_json.read_text(encoding="utf-8"))
    _assert(
        out_payload.get("selected_input_file") == ".cache/airunner/airrunner_heartbeat.v1.json",
        "selected_input_file mismatch (real source preference not applied)",
    )
    _assert(out_payload.get("selected_timestamp_key") == "last_tick_at", "selected_timestamp_key mismatch")
    _assert(
        out_payload.get("selected_threshold_ref") == "heartbeat_stale_seconds_warn",
        "selected_threshold_ref mismatch",
    )

    first = out_json.read_text(encoding="utf-8")
    result2 = run_eval_runner_heartbeat_select(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        out_path=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result2.get("status") == "OK", f"expected OK, got {result2}")
    second = out_json.read_text(encoding="utf-8")
    _assert(first == second, "output not deterministic with fixed timestamp")

    bad_out = run_eval_runner_heartbeat_select(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        out_path="eval_runner_heartbeat_exact_selection.bad.json",
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out path")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    print("OK")


if __name__ == "__main__":
    main()
