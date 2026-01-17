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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.doer_loop_lock import acquire_doer_loop_lock, release_doer_loop_lock

    ws = repo_root / ".cache" / "ws_loop_lock_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    first = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="contract-test",
        owner_session="contract-test",
        run_id="RUN-1",
        ttl_seconds=120,
    )
    if first.get("status") != "OK":
        raise SystemExit("loop_lock_ttl_contract_test failed: initial acquire")

    locked = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="contract-test",
        owner_session="contract-test",
        run_id="RUN-2",
        ttl_seconds=120,
    )
    if locked.get("status") != "LOCKED":
        raise SystemExit("loop_lock_ttl_contract_test failed: expected LOCKED")

    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    lock_obj = _load_json(lock_path)
    lock_obj["expires_at"] = "2000-01-01T00:00:00Z"
    _write_json(lock_path, lock_obj)

    renewed = acquire_doer_loop_lock(
        workspace_root=ws,
        owner_tag="contract-test",
        owner_session="contract-test",
        run_id="RUN-3",
        ttl_seconds=120,
    )
    if renewed.get("status") != "OK":
        raise SystemExit("loop_lock_ttl_contract_test failed: stale clear not acquired")

    release_ok = release_doer_loop_lock(workspace_root=ws, lease_id=str(renewed.get("lease_id") or ""))
    if not release_ok:
        raise SystemExit("loop_lock_ttl_contract_test failed: release failed")


if __name__ == "__main__":
    main()
