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
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_work_intake_disabled(ws: Path) -> None:
    _write_json(
        ws / "policies" / "policy_work_intake.v2.json",
        {
            "version": "v2",
            "enabled": False,
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.auto_loop import run_auto_loop
    from src.ops.decision_inbox import run_decision_seed

    ws = repo_root / ".cache" / "ws_auto_loop_decision_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    _write_work_intake_disabled(ws)

    seed = run_decision_seed(
        workspace_root=ws,
        decision_kind="NETWORK_ENABLE",
        target="github_ops.network_enabled",
    )
    seed_id = seed.get("seed_id")
    if not isinstance(seed_id, str) or not seed_id:
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: seed_id missing")

    result = run_auto_loop(workspace_root=ws, budget_seconds=5, chat=False)
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    if int(counts.get("decision_pending_before") or 0) < 1:
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: pending_before < 1")
    if int(counts.get("bulk_applied_count") or 0) < 1:
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: bulk_applied_count < 1")
    if int(counts.get("decision_pending_after") or 0) != 0:
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: pending_after != 0")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: decision_inbox missing")
    inbox = _load_json(inbox_path)
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    if any(isinstance(item, dict) and item.get("decision_id") == seed_id for item in items):
        raise SystemExit("auto_loop_decision_bulk_contract_test failed: seed still pending")


if __name__ == "__main__":
    main()
