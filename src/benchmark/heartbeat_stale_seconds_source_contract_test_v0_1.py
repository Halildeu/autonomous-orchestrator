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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _load_heartbeat_signal

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "heartbeat_signal_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    heartbeat_path = ws_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    fresh_now = _now_iso()
    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "last_tick_at": "2000-01-01T00:00:00Z",
            "ended_at": fresh_now,
            "last_status": "OK",
        },
    )

    signal = _load_heartbeat_signal(workspace_root=ws_root)
    _assert(signal.get("stale_source_key") == "ended_at", "expected ended_at as stale source")
    _assert(int(signal.get("stale_seconds", 999999)) < 60, "stale_seconds should be near now")

    _write_json(
        heartbeat_path,
        {
            "version": "v1",
            "last_tick_at": "2000-01-01T00:00:00Z",
            "last_status": "OK",
        },
    )
    signal_fallback = _load_heartbeat_signal(workspace_root=ws_root)
    _assert(signal_fallback.get("stale_source_key") == "last_tick_at", "expected fallback to last_tick_at")
    _assert(int(signal_fallback.get("stale_seconds", 0)) > 3600, "stale_seconds should be large")

    print("OK")


if __name__ == "__main__":
    main()
