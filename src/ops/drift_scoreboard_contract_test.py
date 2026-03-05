from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.ops.drift_scoreboard import build_drift_scoreboard, build_drift_scoreboard_summary


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="drift-scoreboard-contract-") as td:
        root = Path(td).resolve()
        core_root = root / "core"
        workspace_root = core_root / ".cache" / "ws_customer_default"
        workspace_root.mkdir(parents=True, exist_ok=True)

        repo_a = root / "repo-a"
        repo_b = root / "repo-b"
        repo_a.mkdir(parents=True, exist_ok=True)
        repo_b.mkdir(parents=True, exist_ok=True)

        _write_json(
            core_root / "standards.lock",
            {
                "version": "v1",
                "managed_repo_sync": {"preserve_existing_paths": ["ci/module_delivery_lanes.v1.json"]},
                "module_delivery_contract": {"required_test_lanes": ["unit", "contract", "integration", "e2e"]},
                "branch_protection": {"default_branch": "main", "required_checks": ["module-delivery-gate"]},
            },
        )

        _write_json(
            workspace_root / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json",
            {
                "version": "v1",
                "mode": "dry-run",
                "target_count": 2,
                "failed_count": 0,
                "results": [
                    {
                        "repo_root": str(repo_a),
                        "status": "OK",
                        "changed_files": 1,
                        "files": [
                            {"path": "ci/module_delivery_lanes.v1.json", "action": "preserve_existing"},
                            {"path": "standards.lock", "action": "would_update"},
                        ],
                    },
                    {
                        "repo_root": str(repo_b),
                        "status": "OK",
                        "changed_files": 0,
                        "files": [
                            {"path": "standards.lock", "action": "no_change"},
                        ],
                    },
                ],
            },
        )

        _write_json(
            repo_a / "ci" / "module_delivery_lanes.v1.json",
            {
                "version": "v1",
                "merge_requires_all_green": True,
                "lanes": {
                    "unit": {"command": "pytest -m unit"},
                    "contract": {"command": "pytest -m contract"},
                    "integration": {"command": "pytest -m integration"},
                    "e2e": {"command": "pytest -m e2e"},
                },
            },
        )
        _write_json(
            repo_b / "ci" / "module_delivery_lanes.v1.json",
            {
                "version": "v1",
                "merge_requires_all_green": True,
                "lanes": {
                    "unit": {"command": "npm run test:unit"},
                    "contract": {"command": "npm run test:contract"},
                    "e2e": {"command": "npm run test:e2e"},
                },
            },
        )

        managed_summary = {
            "status": "WARN",
            "report_path": ".cache/reports/managed_repo_standards_sync/report.v1.json",
            "manifest_path": "",
            "mode": "dry-run",
            "target_count": 2,
            "managed_repo_count": 2,
            "failed_count": 0,
            "drift_pending_count": 1,
            "drift_fixed_count": 0,
            "clean_count": 1,
            "missing_in_report_count": 0,
            "repos": [
                {
                    "repo_root": str(repo_a),
                    "status": "OK",
                    "drift_state": "PENDING",
                    "changed_files": 1,
                    "validation_status": "UNKNOWN",
                },
                {
                    "repo_root": str(repo_b),
                    "status": "OK",
                    "drift_state": "CLEAN",
                    "changed_files": 0,
                    "validation_status": "UNKNOWN",
                },
            ],
            "notes": [],
        }

        scoreboard = build_drift_scoreboard(
            workspace_root=workspace_root,
            core_root=core_root,
            managed_repo_standards_summary=managed_summary,
            max_repos=10,
        )
        summary = build_drift_scoreboard_summary(scoreboard)

        if str(summary.get("status")) != "WARN":
            raise SystemExit("drift_scoreboard_contract_test failed: expected status WARN")
        if int(summary.get("repos_count") or 0) != 2:
            raise SystemExit("drift_scoreboard_contract_test failed: expected repos_count=2")
        if int(summary.get("repos_partial_lane_config") or 0) != 1:
            raise SystemExit("drift_scoreboard_contract_test failed: expected repos_partial_lane_config=1")
        if int(summary.get("branch_unverified_count") or 0) != 2:
            raise SystemExit("drift_scoreboard_contract_test failed: expected branch_unverified_count=2")

        print(
            json.dumps(
                {
                    "status": "OK",
                    "scoreboard_status": summary.get("status"),
                    "repos_count": summary.get("repos_count"),
                    "repos_partial_lane_config": summary.get("repos_partial_lane_config"),
                    "branch_unverified_count": summary.get("branch_unverified_count"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
