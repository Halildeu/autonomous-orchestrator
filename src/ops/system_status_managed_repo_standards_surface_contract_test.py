from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    ws = repo_root / ".cache" / "ws_system_status_managed_repo_standards_surface"
    ws.mkdir(parents=True, exist_ok=True)

    report_path = ws / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json"
    _write_json(
        report_path,
        {
            "version": "v1",
            "mode": "dry-run",
            "target_count": 1,
            "failed_count": 0,
            "results": [
                {
                    "repo_root": "/tmp/repo-1",
                    "status": "OK",
                    "changed_files": 2,
                    "files": [
                        {"path": "standards.lock", "action": "would_update"},
                        {"path": ".github/CODEOWNERS", "action": "would_create"},
                    ],
                }
            ],
        },
    )

    from src.ops.system_status_builder import _load_policy, build_system_status

    policy = _load_policy(repo_root, ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status, dict) else {}
    managed = sections.get("managed_repo_standards") if isinstance(sections, dict) else None
    if not isinstance(managed, dict):
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: section missing")
    if str(managed.get("status")) != "WARN":
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: expected status WARN")
    if int(managed.get("drift_pending_count") or 0) != 1:
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: pending count mismatch")
    if str(managed.get("mode")) != "dry-run":
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: mode mismatch")
    drift = sections.get("drift_scoreboard") if isinstance(sections, dict) else None
    if not isinstance(drift, dict):
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: drift_scoreboard missing")
    if str(drift.get("status")) != "WARN":
        raise SystemExit("system_status_managed_repo_standards_surface_contract_test failed: drift_scoreboard status mismatch")

    print(
        json.dumps(
            {
                "status": "OK",
                "managed_repo_standards_status": managed.get("status"),
                "drift_pending_count": managed.get("drift_pending_count"),
                "drift_scoreboard_status": drift.get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
