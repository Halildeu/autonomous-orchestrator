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

    from src.ops.heartbeat_rule_source_diff import run_heartbeat_rule_source_diff

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "heartbeat_rule_source_diff_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    reports = ws_root / ".cache" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    pinpoint_payload = {
        "version": "v1",
        "eval_runner_read_path": ".cache/airunner/airrunner_heartbeat.v1.json",
        "eval_runner_read_key": "last_tick_at",
        "declared_rule_path": ".cache/airunner/airrunner_heartbeat.v1.json",
        "declared_rule_key": "last_tick_at",
    }
    selection_payload = {
        "version": "v1",
        "selected_input_file": ".cache/airunner/airrunner_heartbeat.v1.json",
        "selected_timestamp_key": "last_tick_at",
    }
    pinpoint_path = reports / "eval_runner_heartbeat_pinpoint.v1.json"
    selection_path = reports / "eval_runner_heartbeat_exact_selection.v1.json"
    _write_json(pinpoint_path, pinpoint_payload)
    _write_json(selection_path, selection_payload)

    result = run_heartbeat_rule_source_diff(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        selection_path=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        out_path=".cache/reports/heartbeat_rule_source_diff.v0.2.json",
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = reports / "heartbeat_rule_source_diff.v0.2.json"
    _assert(out_json.exists(), "output not written")
    out_payload = json.loads(out_json.read_text(encoding="utf-8"))
    _assert(out_payload.get("mismatch") == {"path": False, "key": False}, "mismatch flags incorrect")
    _assert(
        out_payload.get("declared_mismatch") == {"path": False, "key": False},
        "declared mismatch flags incorrect",
    )

    first = out_json.read_text(encoding="utf-8")
    result2 = run_heartbeat_rule_source_diff(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        selection_path=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        out_path=".cache/reports/heartbeat_rule_source_diff.v0.2.json",
        now_iso="2026-01-16T00:00:00Z",
    )
    _assert(result2.get("status") == "OK", f"expected OK, got {result2}")
    second = out_json.read_text(encoding="utf-8")
    _assert(first == second, "output not deterministic with fixed timestamp")

    bad_out = run_heartbeat_rule_source_diff(
        workspace_root=ws_root,
        pinpoint_path=".cache/reports/eval_runner_heartbeat_pinpoint.v1.json",
        selection_path=".cache/reports/eval_runner_heartbeat_exact_selection.v1.json",
        out_path="heartbeat_rule_source_diff.bad.json",
    )
    _assert(bad_out.get("status") == "FAIL", "expected FAIL for invalid out path")
    _assert(bad_out.get("error_code") == "OUT_PATH_INVALID", f"unexpected error_code: {bad_out}")

    print("OK")


if __name__ == "__main__":
    main()
