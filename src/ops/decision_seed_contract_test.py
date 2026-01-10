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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.decision_inbox import run_decision_inbox_build, run_decision_seed

    ws = repo_root / ".cache" / "ws_decision_seed_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    seed_res = run_decision_seed(
        workspace_root=ws,
        decision_kind="NETWORK_ENABLE",
        target="github_ops.network_enabled",
    )
    seed_id = seed_res.get("seed_id")
    if not isinstance(seed_id, str) or not seed_id:
        raise SystemExit("decision_seed_contract_test failed: seed_id missing")

    res = run_decision_inbox_build(workspace_root=ws)
    if res.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("decision_seed_contract_test failed: inbox status invalid")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("decision_seed_contract_test failed: decision_inbox missing")

    inbox = _load_json(inbox_path)
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    if len(items) != 1:
        raise SystemExit("decision_seed_contract_test failed: expected 1 inbox item")
    if items[0].get("decision_id") != seed_id:
        raise SystemExit("decision_seed_contract_test failed: decision_id mismatch")

    first = inbox_path.read_text(encoding="utf-8")
    run_decision_inbox_build(workspace_root=ws)
    second = inbox_path.read_text(encoding="utf-8")
    if first != second:
        raise SystemExit("decision_seed_contract_test failed: output not deterministic")


if __name__ == "__main__":
    main()
