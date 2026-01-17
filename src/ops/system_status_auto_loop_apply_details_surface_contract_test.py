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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_builder import _load_policy, build_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_auto_loop_apply_details_surface_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "auto_loop.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-01T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "counts": {},
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "auto_loop_apply_details.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-01T00:00:00Z",
            "workspace_root": str(ws),
            "counts": {
                "applied": 1,
                "planned": 0,
                "skipped": 0,
                "limit_reached": 0,
                "applied_intake_ids": ["INTAKE-APPLIED-1"],
                "planned_intake_ids": [],
                "limit_reached_intake_ids": [],
            },
            "applied_intake_ids": ["INTAKE-APPLIED-1"],
            "planned_intake_ids": [],
            "limit_reached_intake_ids": [],
        },
    )

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    auto_loop = sections.get("auto_loop") if isinstance(sections.get("auto_loop"), dict) else None
    if not isinstance(auto_loop, dict):
        raise SystemExit("auto_loop_apply_details_surface_contract_test failed: auto_loop section missing")
    if not isinstance(auto_loop.get("last_apply_details_path"), str):
        raise SystemExit("auto_loop_apply_details_surface_contract_test failed: last_apply_details_path missing")
    if not isinstance(auto_loop.get("last_counts"), dict):
        raise SystemExit("auto_loop_apply_details_surface_contract_test failed: last_counts missing")

    report_path = ws / ".cache" / "reports" / "system_status.v1.json"
    _write_json(report_path, system_status)
    ui_snapshot = build_ui_snapshot_bundle(workspace_root=ws)
    if not isinstance(ui_snapshot.get("last_auto_loop_apply_details_path"), str):
        raise SystemExit(
            "auto_loop_apply_details_surface_contract_test failed: ui last_auto_loop_apply_details_path missing"
        )
    if not isinstance(ui_snapshot.get("last_auto_loop_counts"), dict):
        raise SystemExit("auto_loop_apply_details_surface_contract_test failed: ui last_auto_loop_counts missing")


if __name__ == "__main__":
    main()
