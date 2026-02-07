from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.auto_loop import run_auto_loop
    from src.ops.commands.maintenance_lease_cmds import cmd_doer_loop_lock_clear, cmd_doer_loop_lock_seed

    ws = repo_root / ".cache" / "ws_doer_loop_lock_seed_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    args = argparse.Namespace(
        workspace_root=str(ws),
        ttl_seconds="600",
        owner="chat-proof",
        run_id="",
        chat="false",
    )
    rc = cmd_doer_loop_lock_seed(args)
    if rc != 0:
        raise SystemExit("doer_loop_lock_seed_contract_test failed: seed command failed")

    lock_path = ws / ".cache" / "doer" / "doer_loop_lock.v1.json"
    if not lock_path.exists():
        raise SystemExit("doer_loop_lock_seed_contract_test failed: lock file missing")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_lock_id = _hash_text(f"doer-loop-lock-seed-v0.4.1:{ws}:{args.owner}:{int(args.ttl_seconds)}")
    if str(lock.get("lock_id") or "") != expected_lock_id:
        raise SystemExit("doer_loop_lock_seed_contract_test failed: lock_id mismatch")
    if not str(lock.get("expires_at") or ""):
        raise SystemExit("doer_loop_lock_seed_contract_test failed: expires_at missing")

    res = run_auto_loop(workspace_root=ws, budget_seconds=10, chat=False)
    if res.get("status") != "IDLE":
        raise SystemExit("doer_loop_lock_seed_contract_test failed: auto-loop not locked")
    report_rel = res.get("report_path")
    if not isinstance(report_rel, str) or not report_rel.strip():
        raise SystemExit("doer_loop_lock_seed_contract_test failed: report_path missing")
    report_path = (ws / report_rel).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("error_code") != "LOCKED_LOOP":
        raise SystemExit("doer_loop_lock_seed_contract_test failed: expected LOCKED_LOOP")

    clear_args = argparse.Namespace(
        workspace_root=str(ws),
        owner="chat-proof",
        mode="owner_or_stale",
        chat="false",
    )
    rc = cmd_doer_loop_lock_clear(clear_args)
    if rc != 0:
        raise SystemExit("doer_loop_lock_seed_contract_test failed: clear command failed")

    res_ok = run_auto_loop(workspace_root=ws, budget_seconds=10, chat=False)
    report_rel = res_ok.get("report_path")
    if not isinstance(report_rel, str) or not report_rel.strip():
        raise SystemExit("doer_loop_lock_seed_contract_test failed: report_path missing after clear")
    report_path = (ws / report_rel).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("error_code") == "LOCKED_LOOP":
        raise SystemExit("doer_loop_lock_seed_contract_test failed: lock not cleared")


if __name__ == "__main__":
    main()
