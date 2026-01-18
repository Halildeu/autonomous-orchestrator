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

    from src.ops.decision_inbox import run_decision_apply, run_decision_inbox_build, run_decision_seed
    from src.ops.doer_actionability import _decision_allows_auto_apply as actionability_allows
    from src.ops.work_intake_exec_ticket import _decision_allows_auto_apply as exec_allows

    ws = repo_root / ".cache" / "ws_decision_auto_apply_allow_seed_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    target_intake_id = "INTAKE-AUTO-APPLY-ALLOW-SEED-1"

    seed_res = run_decision_seed(
        workspace_root=ws,
        decision_kind="AUTO_APPLY_ALLOW",
        target=target_intake_id,
    )
    seed_id = seed_res.get("seed_id")
    if not isinstance(seed_id, str) or not seed_id:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: seed_id missing")

    res = run_decision_inbox_build(workspace_root=ws)
    if res.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: inbox status invalid")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: decision_inbox missing")

    inbox = _load_json(inbox_path)
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    if not items:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: inbox empty")
    if items[0].get("decision_id") != seed_id:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: decision_id mismatch")

    apply_res = run_decision_apply(workspace_root=ws, decision_id=seed_id, option_id="B")
    if apply_res.get("status") != "OK":
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: apply status not OK")

    applied_path = ws / ".cache" / "index" / "decisions_applied.v1.jsonl"
    if not applied_path.exists():
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: decisions_applied missing")

    applied_records = []
    for line in applied_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            applied_records.append(obj)
    if not applied_records:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: decisions_applied empty")

    # By default, seed ingestion uses SEED:<target> as source_intake_id.
    source_intake_id = str(applied_records[-1].get("source_intake_id") or "")
    expected_source_intake_id = f"SEED:{target_intake_id}"
    if source_intake_id != expected_source_intake_id:
        raise SystemExit(
            "decision_auto_apply_allow_seed_contract_test failed: "
            f"expected source_intake_id={expected_source_intake_id} got {source_intake_id}"
        )

    selection_path = ws / ".cache" / "index" / "work_intake_selection.v1.json"
    if not selection_path.exists():
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: selection file missing")
    selection = _load_json(selection_path)
    selected_ids = selection.get("selected_ids") if isinstance(selection.get("selected_ids"), list) else []
    if target_intake_id not in selected_ids:
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: target intake_id not selected")

    if not exec_allows(applied_records, target_intake_id):
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: exec override not honored")
    if not actionability_allows(applied_records, target_intake_id):
        raise SystemExit("decision_auto_apply_allow_seed_contract_test failed: actionability override not honored")


if __name__ == "__main__":
    main()
