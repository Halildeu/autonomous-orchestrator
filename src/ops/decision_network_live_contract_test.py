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

    from src.ops.decision_inbox import run_decision_apply_bulk, run_decision_inbox_build, run_decision_seed

    ws = repo_root / ".cache" / "ws_decision_network_live_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    run_decision_seed(workspace_root=ws, decision_kind="NETWORK_LIVE_ENABLE", target="NETWORK_LIVE")
    run_decision_inbox_build(workspace_root=ws)

    res = run_decision_apply_bulk(workspace_root=ws, mode="safe_defaults")
    if int(res.get("applied_count") or 0) != 1:
        raise SystemExit("decision_network_live_contract_test failed: applied_count mismatch")

    override_path = ws / ".cache" / "policy_overrides" / "policy_network_live.override.v1.json"
    if not override_path.exists():
        raise SystemExit("decision_network_live_contract_test failed: override missing")

    override = _load_json(override_path)
    if override.get("enabled") is not False:
        raise SystemExit("decision_network_live_contract_test failed: enabled must be false")
    if override.get("enabled_by_decision") is not False:
        raise SystemExit("decision_network_live_contract_test failed: enabled_by_decision must be false")
    if "allow_domains" in override or "allow_actions" in override:
        raise SystemExit("decision_network_live_contract_test failed: allowlist values leaked")
    if not isinstance(override.get("allow_domains_count"), int):
        raise SystemExit("decision_network_live_contract_test failed: allow_domains_count missing")
    if not isinstance(override.get("allow_actions_count"), int):
        raise SystemExit("decision_network_live_contract_test failed: allow_actions_count missing")
    if override.get("decision_option_id") != "A":
        raise SystemExit("decision_network_live_contract_test failed: decision_option_id mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
