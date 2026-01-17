from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
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

    from src.prj_airunner.airunner_tick_admin import run_airunner_watchdog

    ws = repo_root / ".cache" / "ws_airunner_watchdog_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    override_path = ws / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    _write_json(
        override_path,
        {
            "version": "v1",
            "enabled": False,
            "watchdog": {"enabled": True, "heartbeat_stale_seconds": 1, "max_recoveries_per_day": 3},
        },
    )

    heartbeat_path = ws / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    stale_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "generated_at": stale_at.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "last_tick_id": "tick-stale",
            "last_tick_at": stale_at.isoformat().replace("+00:00", "Z"),
            "last_status": "OK",
            "last_error_code": None,
            "last_tick_window": "manual",
            "policy_hash": "test",
            "notes": ["contract_test"],
        },
    )

    res = run_airunner_watchdog(workspace_root=ws)
    if "watchdog_state_path" not in res:
        raise SystemExit("airunner_watchdog_contract_test failed: watchdog_state_path missing")

    fresh_at = datetime.now(timezone.utc)
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "generated_at": fresh_at.isoformat().replace("+00:00", "Z"),
            "workspace_root": str(ws),
            "last_tick_id": "tick-fresh",
            "last_tick_at": fresh_at.isoformat().replace("+00:00", "Z"),
            "last_status": "OK",
            "last_error_code": None,
            "last_tick_window": "manual",
            "policy_hash": "test",
            "notes": ["contract_test"],
        },
    )

    res_fresh = run_airunner_watchdog(workspace_root=ws)
    if res_fresh.get("error_code") != "HEARTBEAT_FRESH":
        raise SystemExit("airunner_watchdog_contract_test failed: expected HEARTBEAT_FRESH")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
