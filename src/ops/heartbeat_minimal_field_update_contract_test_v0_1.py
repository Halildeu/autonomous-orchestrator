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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.operability_heartbeat_reconcile import run_operability_heartbeat_reconcile

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "heartbeat_minimal_ws"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    (ws_root / ".cache" / "airunner").mkdir(parents=True, exist_ok=True)

    canonical_report = ws_root / ".cache" / "reports" / "heartbeat_canonical_path.v0.3.3.json"
    _write_json(
        canonical_report,
        {"version": "v0.3.3", "chosen_path": ".cache/airunner/airrunner_heartbeat.v1.json"},
    )

    pinpoint_report = ws_root / ".cache" / "reports" / "heartbeat_checker_pinpoint.v1.json"
    _write_json(
        pinpoint_report,
        {
            "version": "v1",
            "results": [
                {
                    "path": "src/ops/operability_heartbeat_reconcile.py",
                    "exists": True,
                    "contexts": [{"keys_in_snippet": ["last_tick_at"]}],
                }
            ],
        },
    )

    heartbeat_path = ws_root / ".cache" / "airunner" / "airrunner_heartbeat.v1.json"
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "last_tick_at": "2000-01-01T00:00:00Z",
            "last_status": "STALE",
        },
    )
    before = _read_json(heartbeat_path)

    result = run_operability_heartbeat_reconcile(
        workspace_root=ws_root,
        out_path=".cache/reports/heartbeat_reconcile.contract.v0.1.json",
    )
    _assert(result.get("status") == "OK", f"expected OK, got {result}")

    after = _read_json(heartbeat_path)
    _assert(after.get("last_tick_at") != before.get("last_tick_at"), "last_tick_at not updated")
    _assert(after.get("last_status") == before.get("last_status"), "unexpected non-target field update")

    print("OK")


if __name__ == "__main__":
    main()
