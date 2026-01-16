from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.ops.github_ops_index_lock_local import run_github_ops_index_lock_clear_local  # noqa: E402
from src.ops.operability_heartbeat_reconcile import run_operability_heartbeat_reconcile  # noqa: E402


def _fail(msg: str) -> None:
    print(msg)
    raise SystemExit(1)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> None:
    root = Path(".")
    ws_root = root / ".cache" / "tmp" / "incident_remediation_contract_test_v0_2"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / ".cache" / "reports").mkdir(parents=True, exist_ok=True)

    # index_lock clear local - positive path
    lock_path = ws_root / ".cache" / "index_lock_test" / "index_lock.v1.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("lock", encoding="utf-8")
    old_ts = time.time() - 3600
    os.utime(lock_path, (old_ts, old_ts))

    res = run_github_ops_index_lock_clear_local(
        workspace_root=ws_root,
        out_path=str(ws_root / ".cache" / "reports" / "index_lock_clear_local.v0.2.json"),
        mode="stale_clear",
        max_age_seconds=1,
    )
    if res.get("status") != "OK":
        _fail("index_lock_clear_local status not OK")
    if lock_path.exists():
        _fail("index_lock_clear_local did not clear stale lock")
    if not (ws_root / ".cache" / "reports" / "index_lock_clear_local.v0.2.json").exists():
        _fail("index_lock_clear_local report missing")

    # index_lock clear local - traversal block
    res = run_github_ops_index_lock_clear_local(
        workspace_root=ws_root,
        out_path="../outside.json",
        mode="stale_clear",
        max_age_seconds=1,
    )
    if res.get("status") != "FAIL":
        _fail("index_lock_clear_local traversal not blocked")

    # heartbeat reconcile - positive path
    res = run_operability_heartbeat_reconcile(
        workspace_root=ws_root,
        out_path=str(ws_root / ".cache" / "reports" / "heartbeat_reconcile.v0.2.json"),
    )
    if res.get("status") != "OK":
        _fail("heartbeat_reconcile status not OK")
    heartbeat_path = ws_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    if not heartbeat_path.exists():
        _fail("heartbeat_reconcile did not write heartbeat")
    payload = _read_json(heartbeat_path)
    if not isinstance(payload, dict) or payload.get("last_tick_at") is None:
        _fail("heartbeat payload invalid")

    # heartbeat reconcile - traversal block
    res = run_operability_heartbeat_reconcile(
        workspace_root=ws_root,
        out_path="../bad.json",
    )
    if res.get("status") != "FAIL":
        _fail("heartbeat_reconcile traversal not blocked")

    print("incident_remediation_contract_test_v0_2 ok=true")


if __name__ == "__main__":
    main()
