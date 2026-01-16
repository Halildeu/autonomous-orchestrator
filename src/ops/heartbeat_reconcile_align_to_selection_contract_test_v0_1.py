from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
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


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))
    ws_root = repo_root / ".cache" / "test_tmp" / "heartbeat_reconcile_select_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    reports = ws_root / ".cache" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    selection_payload = {
        "version": "v1",
        "selected_input_file": ".cache/airunner/airrunner_heartbeat.v1.json",
        "selected_timestamp_key": "last_tick_at",
    }
    selection_path = reports / "eval_runner_heartbeat_exact_selection.v1.json"
    _write_json(selection_path, selection_payload)

    heartbeat_path = ws_root / ".cache" / "airunner" / "airrunner_heartbeat.v1.json"
    heartbeat_payload = {"version": "v1", "last_tick_at": "2000-01-01T00:00:00Z"}
    _write_json(heartbeat_path, heartbeat_payload)

    out_path = ".cache/reports/heartbeat_reconcile.v0.1.json"

    from src.ops.operability_heartbeat_reconcile import run_operability_heartbeat_reconcile

    result = run_operability_heartbeat_reconcile(workspace_root=ws_root, out_path=out_path)
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    out_json = reports / "heartbeat_reconcile.v0.1.json"
    _assert(out_json.exists(), "output report not written")

    updated = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    _assert("last_tick_at" in updated, "selected_timestamp_key missing after reconcile")
    _parse_iso(updated["last_tick_at"])

    print("OK")


if __name__ == "__main__":
    main()
