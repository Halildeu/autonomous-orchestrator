from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.auto_loop import run_auto_loop
    from src.ops.system_status_builder import _load_policy, build_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_auto_loop_counts_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    _write_work_intake_disabled(ws)

    run_auto_loop(workspace_root=ws, budget_seconds=5, chat=False)

    auto_loop_path = ws / ".cache" / "reports" / "auto_loop.v1.json"
    apply_path = ws / ".cache" / "reports" / "auto_loop_apply_details.v1.json"
    if not auto_loop_path.exists():
        raise SystemExit("auto_loop_counts_contract_test failed: auto_loop report missing")
    if not apply_path.exists():
        raise SystemExit("auto_loop_counts_contract_test failed: apply_details missing")
    if apply_path.stat().st_mtime < auto_loop_path.stat().st_mtime:
        raise SystemExit("auto_loop_counts_contract_test failed: apply_details not regenerated after auto_loop")

    apply_obj = _load_json(apply_path)
    counts = apply_obj.get("counts") if isinstance(apply_obj.get("counts"), dict) else {}
    applied_ids = counts.get("applied_intake_ids") if isinstance(counts.get("applied_intake_ids"), list) else []
    planned_ids = counts.get("planned_intake_ids") if isinstance(counts.get("planned_intake_ids"), list) else []
    limit_ids = (
        counts.get("limit_reached_intake_ids") if isinstance(counts.get("limit_reached_intake_ids"), list) else []
    )
    if int(counts.get("applied") or 0) != len(applied_ids):
        raise SystemExit("auto_loop_counts_contract_test failed: applied count mismatch")
    if int(counts.get("planned") or 0) != len(planned_ids):
        raise SystemExit("auto_loop_counts_contract_test failed: planned count mismatch")
    if int(counts.get("limit_reached") or 0) != len(limit_ids):
        raise SystemExit("auto_loop_counts_contract_test failed: limit_reached count mismatch")

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    auto_loop = sections.get("auto_loop") if isinstance(sections.get("auto_loop"), dict) else {}
    if auto_loop.get("last_counts") != counts:
        raise SystemExit("auto_loop_counts_contract_test failed: system_status counts mismatch")

    _write_json(ws / ".cache" / "reports" / "system_status.v1.json", system_status)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=ws)
    if ui_snapshot.get("last_auto_loop_counts") != counts:
        raise SystemExit("auto_loop_counts_contract_test failed: ui_snapshot counts mismatch")


if __name__ == "__main__":
    main()
