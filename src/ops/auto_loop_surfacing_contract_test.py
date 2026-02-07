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
    from src.ops.system_status_builder import _load_policy, build_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_auto_loop_surface_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    _write_work_intake_disabled(ws)

    run_auto_loop(workspace_root=ws, budget_seconds=5, chat=False)

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    auto_loop_section = sections.get("auto_loop") if isinstance(sections.get("auto_loop"), dict) else None
    if not isinstance(auto_loop_section, dict):
        raise SystemExit("auto_loop_surfacing_contract_test failed: auto_loop section missing")
    if not isinstance(auto_loop_section.get("last_auto_loop_path"), str):
        raise SystemExit("auto_loop_surfacing_contract_test failed: last_auto_loop_path missing")
    if not isinstance(auto_loop_section.get("last_auto_loop_counts"), dict):
        raise SystemExit("auto_loop_surfacing_contract_test failed: last_auto_loop_counts missing")

    report_path = ws / ".cache" / "reports" / "system_status.v1.json"
    _write_json(report_path, system_status)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=ws)
    if not isinstance(ui_snapshot.get("last_auto_loop_path"), str):
        raise SystemExit("auto_loop_surfacing_contract_test failed: ui last_auto_loop_path missing")


if __name__ == "__main__":
    main()
