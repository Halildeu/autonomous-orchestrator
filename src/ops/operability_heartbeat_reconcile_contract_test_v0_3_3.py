from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)

def _parse_iso(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.operability_heartbeat_reconcile import run_operability_heartbeat_reconcile

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "heartbeat_ws_root"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    (ws_root / ".cache" / "airunner").mkdir(parents=True, exist_ok=True)

    selection_report = ws_root / ".cache" / "reports" / "eval_runner_heartbeat_exact_selection.v1.json"
    _write_json(
        selection_report,
        {
            "version": "v1",
            "selected_input_file": ".cache/airunner/airrunner_heartbeat.v1.json",
            "selected_timestamp_key": "last_tick_at",
        },
    )

    heartbeat_path = ws_root / ".cache" / "airunner" / "airrunner_heartbeat.v1.json"
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "last_tick_at": "2000-01-01T00:00:00Z",
            "ended_at": "2000-01-01T00:00:00Z",
            "last_status": "STALE",
        },
    )

    out_path = ".cache/reports/heartbeat_reconcile.contract.v0.3.3.json"
    result = run_operability_heartbeat_reconcile(workspace_root=ws_root, out_path=out_path)
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    _assert(heartbeat_path.exists(), "heartbeat file not created")
    heartbeat = _read_json(heartbeat_path)
    _assert("last_tick_at" in heartbeat, "heartbeat missing last_tick_at")
    _assert("ended_at" in heartbeat, "heartbeat missing ended_at")
    now = datetime.now(timezone.utc)
    last_tick_at = heartbeat.get("last_tick_at")
    ended_at = heartbeat.get("ended_at")
    _assert(last_tick_at != "2000-01-01T00:00:00Z", "last_tick_at not updated")
    _assert(ended_at != "2000-01-01T00:00:00Z", "ended_at not updated")
    last_tick_dt = _parse_iso(str(last_tick_at))
    ended_dt = _parse_iso(str(ended_at))
    _assert(last_tick_dt is not None, "last_tick_at not parseable")
    _assert(ended_dt is not None, "ended_at not parseable")
    _assert(abs((now - last_tick_dt).total_seconds()) < 30, "last_tick_at not near now")
    _assert(abs((now - ended_dt).total_seconds()) < 30, "ended_at not near now")

    out_report = ws_root / ".cache" / "reports" / "heartbeat_reconcile.contract.v0.3.3.json"
    _assert(out_report.exists(), "reconcile report not created")

    selection_report.unlink()
    result_missing = run_operability_heartbeat_reconcile(workspace_root=ws_root, out_path=out_path)
    _assert(result_missing.get("status") == "FAIL", "expected FAIL when selection missing")
    _assert(
        result_missing.get("error_code") == "SELECTION_MISSING",
        f"unexpected error_code: {result_missing}",
    )

    print("OK")


if __name__ == "__main__":
    main()
