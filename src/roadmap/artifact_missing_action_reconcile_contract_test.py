from __future__ import annotations

import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    import sys

    sys.path.insert(0, str(repo_root))

    from src.roadmap.orchestrator_artifacts import (
        _artifact_missing_action,
        _reconcile_artifact_missing_actions,
    )

    missing_item = {
        "id": "session_context",
        "path": ".cache/sessions/default/session_context.v1.json",
        "owner_milestone": "M3.5",
        "severity": "warn",
        "auto_heal": True,
    }
    tracked_action = _artifact_missing_action(missing_item)
    register = {
        "actions": [
            tracked_action,
            {
                "action_id": "keep-other",
                "kind": "PLACEHOLDER_MILESTONE",
                "message": "placeholder",
                "resolved": False,
            },
        ]
    }

    # Artifact mevcut ise stale DERIVED_ARTIFACT_MISSING kaydı resolve edilmelidir.
    res = _reconcile_artifact_missing_actions(actions_reg=register, current_missing=[])
    if not res.get("changed"):
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected changed=true")
    if int(res.get("resolved_count") or 0) != 1:
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected resolved_count=1")
    if register["actions"][0].get("resolved") is not True:
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected resolved action")

    # Artifact tekrar missing olduğunda kayıt yeniden unresolved olmalıdır.
    res2 = _reconcile_artifact_missing_actions(actions_reg=register, current_missing=[missing_item])
    if not res2.get("changed"):
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected reopen changed=true")
    if int(res2.get("reopened_count") or 0) != 1:
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected reopened_count=1")
    if register["actions"][0].get("resolved") is True:
        raise SystemExit("artifact_missing_action_reconcile_contract_test failed: expected unresolved action")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
