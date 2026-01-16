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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _parse_iso(value: str) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(value)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.airunner_tick_utils import _write_heartbeat

    ws_root = repo_root / ".cache" / "test_tmp" / "airunner_heartbeat_writer_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    heartbeat_path = ws_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"

    _write_heartbeat(
        heartbeat_path,
        workspace_root=ws_root,
        tick_id="TICK-TEST-001",
        status="IDLE",
        error_code=None,
        window_bucket="CONTRACT",
        policy_hash="hash",
        notes=["contract"],
    )

    _assert(heartbeat_path.exists(), "heartbeat file not written")
    payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    ended_at = payload.get("ended_at")
    _assert(isinstance(ended_at, str) and ended_at, "ended_at missing")
    dt = _parse_iso(ended_at)
    _assert(dt is not None, "ended_at not parseable RFC3339")

    now = datetime.now(timezone.utc)
    delta = abs((now - dt).total_seconds())
    _assert(delta < 10, "ended_at not close to now")

    print("OK")


if __name__ == "__main__":
    main()
