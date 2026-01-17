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

    from src.ops.work_item_leases import acquire_lease, release_lease, load_leases

    ws = repo_root / ".cache" / "ws_lease_lifecycle_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    item_id = "LEASE-ITEM-001"
    owner = "contract-test"

    first = acquire_lease(
        workspace_root=ws,
        work_item_id=item_id,
        run_id="RUN-1",
        owner=owner,
        ttl_seconds=120,
    )
    if first.get("status") != "ACQUIRED":
        raise SystemExit("lease_lifecycle_contract_test failed: acquire status")

    locked = acquire_lease(
        workspace_root=ws,
        work_item_id=item_id,
        run_id="RUN-2",
        owner=owner,
        ttl_seconds=120,
    )
    if locked.get("status") != "LOCKED":
        raise SystemExit("lease_lifecycle_contract_test failed: expected LOCKED")

    lease_path = ws / ".cache" / "index" / "work_item_leases.v1.json"
    lease_obj = _load_json(lease_path)
    leases = lease_obj.get("leases") if isinstance(lease_obj.get("leases"), list) else []
    if not leases:
        raise SystemExit("lease_lifecycle_contract_test failed: lease missing")
    leases[0]["expires_at"] = "2000-01-01T00:00:00Z"
    lease_obj["leases"] = leases
    _write_json(lease_path, lease_obj)

    renewed = acquire_lease(
        workspace_root=ws,
        work_item_id=item_id,
        run_id="RUN-3",
        owner=owner,
        ttl_seconds=120,
    )
    if renewed.get("status") != "ACQUIRED" or not isinstance(renewed.get("stale_cleared"), dict):
        raise SystemExit("lease_lifecycle_contract_test failed: stale clear not detected")

    released = release_lease(workspace_root=ws, work_item_id=item_id, run_id="RUN-3", owner=owner)
    if released.get("status") != "RELEASED":
        raise SystemExit("lease_lifecycle_contract_test failed: release status")

    if any(lease.get("work_item_id") == item_id for lease in load_leases(ws)):
        raise SystemExit("lease_lifecycle_contract_test failed: lease still present after release")


if __name__ == "__main__":
    main()
