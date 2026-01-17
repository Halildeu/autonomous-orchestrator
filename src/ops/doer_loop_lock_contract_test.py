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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.doer_loop_lock import acquire_doer_loop_lock, release_doer_loop_lock

    ws = repo_root / ".cache" / "ws_doer_loop_lock_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res1 = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="tester",
        run_id="run-1",
        ttl_seconds=300,
    )
    if res1.get("status") != "OK":
        raise SystemExit("doer_loop_lock_contract_test failed: initial lock not acquired")

    res2 = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="tester",
        run_id="run-2",
        ttl_seconds=300,
    )
    if res2.get("status") != "LOCKED":
        raise SystemExit("doer_loop_lock_contract_test failed: second lock not blocked")

    if not release_doer_loop_lock(workspace_root=ws, lease_id=str(res1.get("lease_id") or "")):
        raise SystemExit("doer_loop_lock_contract_test failed: release failed")

    res3 = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="tester",
        run_id="run-3",
        ttl_seconds=300,
    )
    if res3.get("status") != "OK":
        raise SystemExit("doer_loop_lock_contract_test failed: lock not reacquired after release")

    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    _write_json(
        lock_path,
        {
            "version": "v1",
            "lease_id": "stale",
            "owner_tag": "tester",
            "run_id": "run-stale",
            "acquired_at": expired,
            "expires_at": expired,
            "heartbeat_at": expired,
        },
    )
    res4 = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="tester",
        run_id="run-4",
        ttl_seconds=300,
    )
    if res4.get("status") != "OK":
        raise SystemExit("doer_loop_lock_contract_test failed: stale lock not cleared")

    stale_report = ws / ".cache" / "reports" / "doer_loop_lock_clear_stale.v1.json"
    if not stale_report.exists():
        raise SystemExit("doer_loop_lock_contract_test failed: stale clear report missing")


if __name__ == "__main__":
    main()
