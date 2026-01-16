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

    from src.prj_airunner.airunner_auto_mode import run_auto_mode_actions
    from src.prj_airunner.auto_mode_dispatch import _policy_defaults

    ws = repo_root / ".cache" / "ws_doer_network_gate_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    dispatch_plan = {
        "dispatched_extensions": ["PRJ-GITHUB-OPS"],
        "job_candidates": [
            {
                "extension_id": "PRJ-GITHUB-OPS",
                "job_kind": "PR_OPEN",
                "intake_id": "INTAKE-NET-1",
            }
        ],
        "selected_ids": [],
        "plan_candidates": [],
    }
    evidence_paths: list[str] = []
    ops_called: list[str] = []
    notes: list[str] = []
    res = run_auto_mode_actions(
        workspace_root=ws,
        dispatch_plan=dispatch_plan,
        auto_mode_policy=_policy_defaults(),
        allowed_ops=[],
        can_start_github=True,
        can_start_deploy=True,
        max_dispatch_jobs=1,
        max_dispatch_actions=1,
        perf_cfg={},
        work_intake_path=None,
        evidence_paths=evidence_paths,
        ops_called=ops_called,
        notes=notes,
    )

    if res.get("dispatch_jobs_started") != 0:
        raise SystemExit("doer_network_gate_contract_test failed: job started unexpectedly")
    if res.get("dispatch_idle_reason") != "BLOCKED_BY_DECISION":
        raise SystemExit("doer_network_gate_contract_test failed: idle reason mismatch")
    if "github-ops-job-start" in ops_called or "deploy-job-start" in ops_called:
        raise SystemExit("doer_network_gate_contract_test failed: job-start should be skipped")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("doer_network_gate_contract_test failed: decision_inbox missing")
    inbox = _load_json(inbox_path)
    items = inbox.get("items") if isinstance(inbox, dict) else []
    if not any(
        isinstance(item, dict) and item.get("decision_kind") == "NETWORK_LIVE_ENABLE"
        for item in (items if isinstance(items, list) else [])
    ):
        raise SystemExit("doer_network_gate_contract_test failed: NETWORK_LIVE_ENABLE decision missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
